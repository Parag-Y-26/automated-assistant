import os
import sys
import yaml
import logging
import uuid
import time
import asyncio
import pyperclip
import pygetwindow as gw
from aioconsole import ainput
from rich.console import Console

logger = logging.getLogger("ladas")

# LADAS Modules
from capture.capture_manager import CaptureManager
from perception.ocr_engine import OCREngine
from perception.vision_detector import VisionDetector
from perception.state_builder import StateBuilder
from planning.task_planner import TaskPlanner
from reasoning.instruction_parser import InstructionParser
from reasoning.decision_engine import DecisionEngine
from reasoning.llm_client import LLMClient
from reasoning.mock_llm import MockLLMClient
from execution.action_executor import ActionExecutor
from execution.failsafe_monitor import failsafe, FailsafeTriggered
from memory.database import Database
from memory.task_store import TaskStore
from memory.action_log import ActionLog
from state.fsm import StateTracker, FSMState
from config_utils import validate_config

# Setup rich console for terminal output
console = Console()

class LADAS:
    def __init__(self, config_path: str = "config.yaml"):
        # 1. Load Config
        candidate_paths = [config_path]
        if not os.path.isabs(config_path):
            candidate_paths.append(os.path.join(os.path.dirname(__file__), config_path))
            candidate_paths.append(os.path.join(os.path.dirname(__file__), "config.yaml"))

        resolved_config_path = None
        for p in candidate_paths:
            if p and os.path.exists(p):
                resolved_config_path = p
                break

        if not resolved_config_path:
            console.print(
                "[bold red]Config file not found. Tried:\n" + "\n".join(f"- {p}" for p in candidate_paths) + "\nExiting.[/bold red]"
            )
            sys.exit(1)
            
        with open(resolved_config_path, "r") as f:
            raw_config = yaml.safe_load(f) or {}
            self.config = validate_config(raw_config)
            
        # 2. Setup Logging
        os.makedirs("logs", exist_ok=True)
        if not logger.hasHandlers():
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
            
            fh = logging.FileHandler(f"logs/ladas_system_{int(time.time())}.log")
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        
        # 3. Initialize Memory
        self.db = Database("memory.db")
        self.task_store = TaskStore(self.db)
        self.action_log = ActionLog(self.db)
        
        # 4. Initialize State Tracker
        self.state = StateTracker()
        self.state.context_buffer = {
            "active_window": "",
            "clipboard": ""
        }
        
        # 5. Initialize Hardware Interfaces
        console.print("[yellow]Initializing Screen Capture & Failsafe...[/yellow]")
        self.capture = CaptureManager(self.config)
        failsafe.start()
        
        # 6. Initialize Models
        console.print("[yellow]Initializing Models (LLM, Vision, OCR)...[/yellow]")
        llm_model = self.config.get("reasoning", {}).get("default_nim_model", "meta/llama-3.1-70b-instruct")
        try:
            self.llm = LLMClient(model_name=llm_model) 
        except Exception as e:
            logger.exception("Failed to initialize LLMClient")
            allow_mock = self.config.get("system", {}).get("allow_mock_on_startup_failure", False)
            if allow_mock:
                self.llm = MockLLMClient()
                console.print("[yellow]Warning: Using MockLLMClient due to failure.[/yellow]")
            else:
                console.print("[bold red]Failed to initialize LLM. Configuration forbids mock fallback. See logs for details.[/bold red]")
                sys.exit(1)
        
        self.parser = InstructionParser(self.llm, self.config)
        self.planner = TaskPlanner(self.llm, self.config)
        self.decision = DecisionEngine(self.llm, self.config)
        
        self.ocr = OCREngine(self.config)
        self.vision = VisionDetector(self.config)
        self.executor = ActionExecutor(self.config)
        
        self.session_id = uuid.uuid4().hex[:8]
        self._validate_startup()
        console.print(f"[green]Initialization Complete. Session: {self.session_id}[/green]")

    def _validate_startup(self):
        """Validates critical dependencies before starting."""
        allow_mock = self.config.get("system", {}).get("allow_mock_on_startup_failure", False)
        # Check YOLO Model
        yolo_path = self.config.get("perception", {}).get("vision", {}).get("yolo_model_path", "yolov8n.pt")
        if not os.path.exists(yolo_path):
            error_msg = f"YOLO model not found at '{yolo_path}'."
            logger.error(error_msg)
            if allow_mock:
                console.print(f"[yellow]{error_msg} (Continuing without YOLO)[/yellow]")
            else:
                console.print(f"[bold red]{error_msg}[/bold red]")
                sys.exit(1)
        logger.info("Startup validation passed successfully.")

    async def _context_updater_daemon(self):
        """
        Agentic Asynchronous Execution: "Rolling Context Buffer" 
        Asynchronously aggregates cross-context awareness (clipboard contents, active window).
        Runs permanently in the background.
        """
        while True:
            try:
                # Active window retrieval
                active_win = await asyncio.to_thread(gw.getActiveWindow)
                if active_win:
                    self.state.context_buffer["active_window"] = getattr(active_win, "title", "")
                
                # Clipboard retrieval (truncated for context limits)
                clip = await asyncio.to_thread(pyperclip.paste)
                if clip and clip != self.state.context_buffer.get("clipboard"):
                    self.state.context_buffer["clipboard"] = clip[:1000]
            except Exception as e:
                logger.debug(f"Context Daemon ignored error: {e}")
            
            await asyncio.sleep(2.0)

    async def run_terminal_loop(self):
        """The main async interactive terminal loop (Comet Paradigm)."""
        console.print(r"""
╔══════════════════════════════════════════════════════════════╗
║     LOCAL AI DESKTOP AUTOMATION SYSTEM v2.0 (ASYNC NIM)      ║
╚══════════════════════════════════════════════════════════════╝
        """, style="bold cyan")
        
        # Fire and forget the context aggregation daemon
        daemon_task = asyncio.create_task(self._context_updater_daemon())
        
        # To handle cancellation
        active_tasks = []
        
        try:
            while True:
                console.print(f"\n[bold green]\\[READY][/bold green] Enter command (type 'quit' to exit):")
                user_input = await ainput("> ")
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                if user_input.lower() in ["quit", "exit"]:
                    self._shutdown()
                    break
                    
                # Comet Paradigm: Fire task execution concurrently in the background so the terminal
                # doesn't block, allowing user to interact and the UI to remain responsive.
                task = asyncio.create_task(self._execute_task(user_input))
                active_tasks.append(task)
                
        except asyncio.CancelledError:
            console.print("\n[yellow]Loop cancelled. Shutting down...[/yellow]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Keyboard interrupt. Shutting down...[/yellow]")
        finally:
            daemon_task.cancel()
            for t in active_tasks:
                if not t.done():
                    t.cancel()
            self._shutdown()

    async def _execute_task(self, instruction: str):
        """The core execution lifecycle implemented asynchronously."""
        # Using a fresh StateTracker for concurrency safety is ideal, but for now we reset the global
        self.state.reset()
        self.state.session_id = self.session_id
        self.state.task_id = f"task_{int(time.time())}"
        
        self.state.transition_to(FSMState.PARSING)
        console.print("[dim cyan]\\[PARSING][/dim cyan] Interpreting instruction...")
        
        try:
             intent = await asyncio.to_thread(self.parser.parse, instruction, self.state)
        except Exception as e:
             logger.error(f"Fatal error during instruction parsing: {e}")
             console.print(f"[bold red]\\[FATAL ERROR][/bold red] Instruction parsing failed: {e}")
             self.state.transition_to(FSMState.FAILED)
             self.task_store.update_task_status(self.state.task_id, self.state.fsm_state.name)
             return
        
        await asyncio.to_thread(self.task_store.create_task, self.session_id, self.state.task_id, instruction)
        
        self.state.transition_to(FSMState.PLANNING)
        console.print("[dim cyan]\\[PLANNING][/dim cyan] Generating step plan...")
        
        try:
             plan = await asyncio.to_thread(self.planner.generate_plan, intent, self.state)
        except Exception as e:
             logger.error(f"Fatal error during plan generation: {e}")
             console.print(f"[bold red]\\[FATAL ERROR][/bold red] Plan generation failed: {e}")
             self.state.transition_to(FSMState.FAILED)
             self.task_store.update_task_status(self.state.task_id, self.state.fsm_state.name)
             return
             
        self.state.plan = plan
        await asyncio.to_thread(self.task_store.update_task_plan, self.state.task_id, intent.get("parsed_goal", ""), plan)
        
        console.print("\n[bold]Task Plan:[/bold]")
        for i, step in enumerate(plan.get("steps", [])):
            console.print(f"  Step {i+1}: {step.get('description', 'Unknown')}")
        print()
            
        # 3. Execution Loop
        steps = plan.get("steps") or []
        if not steps:
            logger.info("Plan contains no steps. Transitioning to TASK_COMPLETE.")
            console.print("[yellow]Plan contains no steps. Ending task.[/yellow]")
            self.state.transition_to(FSMState.TASK_COMPLETE)
            await asyncio.to_thread(self.task_store.update_task_status, self.state.task_id, self.state.fsm_state.name)
            return

        if not self.state.advance_step():
             return 
             
        global_timeout = self.config.get("planning", {}).get("global_timeout_seconds", 1800)
        self.state.task_start_time = time.time()
        
        try:
            while self.state.fsm_state in [FSMState.EXECUTING, FSMState.VALIDATING, FSMState.RETRYING]:
                
                if self.state.fsm_state == FSMState.RETRYING:
                    self.state.transition_to(FSMState.EXECUTING)
                    
                if time.time() - self.state.task_start_time > global_timeout:
                    self.state.transition_to(FSMState.TIMEOUT)
                    console.print(f"\n[bold red]\\[TIMEOUT][/bold red] Global timeout exceeded.")
                    break
                    
                await asyncio.to_thread(failsafe.check)
                
                step = self.state.get_current_step()
                if not step:
                    self.state.transition_to(FSMState.TASK_COMPLETE)
                    break
                    
                console.print(f"[blue]\\[EXECUTING][/blue] {step.get('description', 'Unknown Step')}")
                
                # Capture Screen
                capture_retries = 3
                cap_data, dims = None, None
                for attempt in range(1, capture_retries + 1):
                    try:
                        cap_data = await asyncio.to_thread(self.capture.capture_screen, self.session_id, self.state.current_step_id)
                        dims = await asyncio.to_thread(self.capture.get_monitor_dimensions)
                        break
                    except Exception:
                        if attempt < capture_retries:
                            await asyncio.sleep(0.5)

                if not cap_data or not dims:
                    console.print("[bold red]Screen capture failed. Aborting task.[/bold red]")
                    self.state.transition_to(FSMState.FAILED)
                    break

                screen_path = cap_data["path"]
                screen_hash = cap_data["hash"]
                
                # Check Infinite Loop
                history = await asyncio.to_thread(self.action_log.get_recent_actions, self.state.task_id)
                last_act = history[-1]["action_type"] if history else None
                is_static_expected = last_act in ["wait", "run_command", "scroll", "search_web"]
                
                is_loop = await asyncio.to_thread(self.capture.check_loop, screen_hash)
                if is_loop:
                    if not is_static_expected:
                        self.state.repeated_state_count += 1
                        if self.state.repeated_state_count >= self.config.get("state", {}).get("repeated_state_limit", 5):
                            console.print("[yellow]\\[WARNING][/yellow] Infinite loop detected. Aborting task safely.")
                            self.state.transition_to(FSMState.TASK_COMPLETE)
                            break
                else:
                    self.state.repeated_state_count = 0
                    
                # Perception Pipeline
                try:
                    ocr_data = await asyncio.to_thread(self.ocr.process_image, screen_path, self.state.current_step_id)
                except Exception:
                    ocr_data = []
                    
                try:
                    vis_data = await asyncio.to_thread(self.vision.detect_elements, screen_path, self.state.current_step_id)
                except Exception:
                    vis_data = []
                
                try:
                    screen_state = await asyncio.to_thread(
                        StateBuilder.build_screen_state,
                        self.session_id, self.state.current_step_id,
                        self.config.get("capture", {}).get("monitor_index", 0),
                        self.config.get("capture", {}).get("capture_region", None),
                        dims, screen_hash, ocr_data, vis_data
                    )
                    # Inject asynchronously aggregated context daemon states into perception context window
                    screen_state["context_buffer"] = self.state.context_buffer
                except Exception:
                    screen_state = {"resolution": dims, "elements": [], "text_regions": [], "screenshot_path": screen_path}
                
                # Action Decision
                try:
                     action_cmd = await asyncio.to_thread(
                         self.decision.get_next_action,
                         intent, step, self.state.current_step_idx, len(self.state.plan["steps"]), screen_state, history, self.state
                     )
                except Exception:
                     self.state.step_retry_count += 1
                     if self.state.step_retry_count > 1:
                          self.state.transition_to(FSMState.STEP_FAILED)
                          continue
                     action_cmd = {"action_type": "wait", "parameters": {"duration_ms": 1000}, "reasoning": "Mock fallback"}
                     
                console.print(f"  ├─ Action: {action_cmd.get('action_type')} | Reason: {action_cmd.get('reasoning')}")
                
                # Action Execution
                try:
                    action_result = await self.executor.execute(action_cmd)
                    if action_result and action_cmd.get("action_type") == "search_web":
                        # Autonomous web retrieval injection back into context log
                        action_cmd["action_result"] = action_result
                except Exception as e:
                    logger.exception(f"Executor failed for action: {action_cmd}")
                    self.state.step_retry_count += 1
                    retry_limit = self.config.get("execution", {}).get("step_retry_limit", 3)
                    if self.state.step_retry_count > retry_limit:
                        await asyncio.to_thread(self.task_store.update_step_status, self.state.task_id, self.state.current_step_id, "FAILED", self.state.step_retry_count)
                        if not self.state.advance_step():
                            break
                    else:
                        console.print(f"[yellow]  └─ Status: ⚠ Action failed. Retrying ({self.state.step_retry_count}/{retry_limit})...[/yellow]")
                    await asyncio.sleep(1.5)
                    continue
                
                # Log Action (Now includes Perplexity searches seamlessly for reasoning context window)
                await asyncio.to_thread(self.action_log.log_action, self.session_id, self.state.task_id, self.state.current_step_id, action_cmd, screen_hash)
                
                # Real result validation
                post_wait = max(action_cmd.get("post_action_wait_ms", 500) / 1000.0, 0.5)
                await asyncio.sleep(post_wait)
                
                self.state.transition_to(FSMState.VALIDATING)
                post_cap_data = None
                for attempt in range(1, 3):
                    try:
                        post_cap_data = await asyncio.to_thread(self.capture.capture_screen, self.session_id, f"{self.state.current_step_id}_post")
                        break
                    except Exception:
                        await asyncio.sleep(0.3)
                
                no_change_ok = action_cmd.get("action_type", "") in ("wait", "scroll", "hover", "move", "press_key", "search_web")
                
                if post_cap_data:
                    post_hash = post_cap_data["hash"]
                    screen_unchanged = await asyncio.to_thread(self.capture.check_loop, post_hash)
                
                    if screen_unchanged and not no_change_ok:
                        self.state.step_retry_count += 1
                        retry_limit = self.config.get("execution", {}).get("step_retry_limit", 3)
                        if self.state.step_retry_count <= retry_limit:
                            delay = min(self.config.get("state", {}).get("base_delay", 1.0) * (2 ** self.state.step_retry_count), self.config.get("state", {}).get("max_delay", 30.0))
                            self.state.transition_to(FSMState.RETRYING)
                            await asyncio.sleep(delay)
                            continue
                        else:
                            await asyncio.to_thread(self.task_store.update_step_status, self.state.task_id, self.state.current_step_id, "FAILED", self.state.step_retry_count)
                    else:
                        console.print(f"  └─ [green]✓ Step complete[/green]")
                        await asyncio.to_thread(self.task_store.update_step_status, self.state.task_id, self.state.current_step_id, "COMPLETED", self.state.step_retry_count)
                else:
                    console.print("  └─ [yellow]✓ Step assumed complete (post-capture failed)[/yellow]")
                
                if not self.state.advance_step():
                    break
                    
                idle_sleep = self.config.get("system", {}).get("loop_idle_sleep_ms", 100) / 1000.0
                await asyncio.sleep(idle_sleep)
                    
        except asyncio.CancelledError:
             console.print("\n[bold red]\\[ABORTED] Task cancelled.[/bold red]")
             self.state.transition_to(FSMState.ABORTED)
        except FailsafeTriggered:
            self.state.transition_to(FSMState.ABORTED)
            console.print("\n[bold red]\\[ABORTED][/bold red] Failsafe triggered by user. Task stopped.")
        except Exception as e:
            logger.exception(f"Task execution failed: {e}")
            self.state.transition_to(FSMState.FAILED)
            console.print(f"\n[bold red]\\[ERROR][/bold red] {e}")
            
        finally:
            await asyncio.to_thread(self.task_store.update_task_status, self.state.task_id, self.state.fsm_state.name)
            await asyncio.to_thread(self.capture.task_complete, self.session_id)
            if self.state.fsm_state == FSMState.TASK_COMPLETE:
                 console.print(f"\n[bold green]\\[COMPLETE][/bold green] Task finished successfully.")
                 # Print > prompt naturally since it might just finish in the background
                 console.print("\n[bold green]\\[READY][/bold green] Enter command (type 'quit' to exit):")

    def _shutdown(self):
        console.print("[yellow]Cleaning up processes...[/yellow]")
        failsafe.stop()
        self.capture.shutdown()
        console.print("Goodbye.")
        
if __name__ == "__main__":
    app = LADAS()
    try:
        asyncio.run(app.run_terminal_loop())
    except KeyboardInterrupt:
        pass
