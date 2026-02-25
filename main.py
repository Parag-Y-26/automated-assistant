import os
import sys
import yaml
import logging
import uuid
import time
from rich.console import Console

# LADAS Modules
from capture.capture_manager import CaptureManager
from perception.ocr_engine import OCREngine
from perception.vision_detector import VisionDetector
from perception.state_builder import StateBuilder
from planning.task_planner import TaskPlanner
from reasoning.instruction_parser import InstructionParser
from reasoning.decision_engine import DecisionEngine
from reasoning.llm_client import LLMClient
from execution.action_executor import ActionExecutor
from execution.failsafe_monitor import failsafe, FailsafeTriggered
from memory.database import Database
from memory.task_store import TaskStore
from memory.action_log import ActionLog
from state.fsm import StateTracker, FSMState

# Setup rich console for terminal output
console = Console()

class LADAS:
    def __init__(self, config_path: str = "config.yaml"):
        # 1. Load Config
        if not os.path.exists(config_path):
            console.print(f"[bold red]Config file not found at {config_path}. Exiting.[/bold red]")
            sys.exit(1)
            
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        # 2. Setup Logging
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            filename=f"logs/ladas_system_{int(time.time())}.log",
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        
        # 3. Initialize Memory
        # (Using a single DB for testing. In prod, you might scope by session)
        self.db = Database("memory.db")
        self.task_store = TaskStore(self.db)
        self.action_log = ActionLog(self.db)
        
        # 4. Initialize State Tracker
        self.state = StateTracker()
        
        # 5. Initialize Hardware Interfaces
        console.print("[yellow]Initializing Screen Capture & Failsafe...[/yellow]")
        self.capture = CaptureManager(self.config)
        failsafe.start()
        
        # 6. Initialize Models (These take time/memory)
        console.print("[yellow]Initializing Models (LLM, Vision, OCR)...[/yellow]")
        # Mock LLM for now if path is missing to avoid crashing
        llm_path = self.config.get("reasoning", {}).get("model_path", "")
        # For a full implementation, proper paths must be set
        self.llm = LLMClient(model_path=llm_path) 
        
        self.parser = InstructionParser(self.llm)
        self.planner = TaskPlanner(self.llm)
        self.decision = DecisionEngine(self.llm)
        
        self.ocr = OCREngine(self.config)
        self.vision = VisionDetector(self.config)
        
        self.executor = ActionExecutor(self.config)
        
        self.session_id = uuid.uuid4().hex[:8]
        console.print(f"[green]Initialization Complete. Session: {self.session_id}[/green]")

    def run_terminal_loop(self):
        """The main interactive terminal loop."""
        console.print(r"""
╔══════════════════════════════════════════════════════════════╗
║          LOCAL AI DESKTOP AUTOMATION SYSTEM v1.0             ║
╚══════════════════════════════════════════════════════════════╝
        """, style="bold cyan")
        
        while True:
            try:
                self.state.reset()
                self.state.session_id = self.session_id
                console.print(f"\n[bold green]\[READY][/bold green] Enter command (type 'quit' to exit):")
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                if user_input.lower() in ["quit", "exit"]:
                    self._shutdown()
                    break
                    
                self._execute_task(user_input)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Keyboard interrupt. Shutting down...[/yellow]")
                self._shutdown()
                break

    def _execute_task(self, instruction: str):
        """The core execution lifecycle for a single task."""
        self.state.task_id = f"task_{int(time.time())}"
        
        # 1. Parsing
        self.state.transition_to(FSMState.PARSING)
        console.print("[dim cyan]\[PARSING][/dim cyan] Interpreting instruction...")
        
        # Try-catch blocks mock actual LLM call which might fail without model
        try:
             intent = self.parser.parse(instruction)
        except Exception:
             intent = {
                  "task_id": self.state.task_id, 
                  "raw_instruction": instruction,
                  "parsed_goal": instruction
             }
        
        self.task_store.create_task(self.session_id, self.state.task_id, instruction)
        
        # 2. Planning
        self.state.transition_to(FSMState.PLANNING)
        console.print("[dim cyan]\[PLANNING][/dim cyan] Generating step plan...")
        
        try:
             plan = self.planner.generate_plan(intent)
        except Exception:
             # Stub plan
             plan = {
                  "steps": [{
                       "step_id": "step_1",
                       "description": "Execute user command",
                       "max_retries": 1
                  }]
             }
             
        self.state.plan = plan
        self.task_store.update_task_plan(self.state.task_id, intent.get("parsed_goal", ""), plan)
        
        console.print("\n[bold]Task Plan:[/bold]")
        for i, step in enumerate(plan.get("steps", [])):
            console.print(f"  Step {i+1}: {step.get('description', 'Unknown')}")
        print()
            
        # 3. Execution Loop
        if not self.state.advance_step():
             return # Empty plan
             
        global_timeout = self.config.get("planning", {}).get("global_timeout_seconds", 1800)
        self.state.task_start_time = time.time()
        
        try:
            while self.state.fsm_state in [FSMState.EXECUTING, FSMState.VALIDATING, FSMState.RETRYING]:
                
                if time.time() - self.state.task_start_time > global_timeout:
                    self.state.transition_to(FSMState.TIMEOUT)
                    console.print(f"\n[bold red]\[TIMEOUT][/bold red] Global timeout exceeded.")
                    break
                    
                failsafe.check()
                
                step = self.state.get_current_step()
                console.print(f"[blue]\[EXECUTING][/blue] {step['description']}")
                
                # Capture Screen
                cap_data = self.capture.capture_screen(self.session_id, self.state.current_step_id)
                screen_path = cap_data["path"]
                screen_hash = cap_data["hash"]
                dims = self.capture.get_monitor_dimensions()
                
                # Check for Infinite Loop
                if self.capture.check_loop(screen_hash):
                    self.state.repeated_state_count += 1
                    if self.state.repeated_state_count >= self.config.get("state", {}).get("repeated_state_limit", 5):
                        console.print("[yellow]\[WARNING][/yellow] Infinite loop detected. Aborting step.")
                        self.state.transition_to(FSMState.STEP_FAILED)
                        continue
                else:
                    self.state.repeated_state_count = 0
                    
                # Perception Pipeline
                ocr_data = self.ocr.process_image(screen_path, self.state.current_step_id)
                vis_data = self.vision.detect_elements(screen_path, self.state.current_step_id)
                
                screen_state = StateBuilder.build_screen_state(
                    self.session_id, self.state.current_step_id,
                    self.config.get("capture", {}).get("monitor_index", 0),
                    self.config.get("capture", {}).get("capture_region", None),
                    dims, screen_hash, ocr_data, vis_data
                )
                
                # Action Decision
                history = self.action_log.get_recent_actions(self.state.task_id)
                try:
                     action_cmd = self.decision.get_next_action(
                         step, self.state.current_step_idx, len(self.state.plan["steps"]), screen_state, history)
                except Exception:
                     # Mock decision for testing if LLM fails
                     action_cmd = {
                          "action_type": "wait",
                          "parameters": {"duration_ms": 1000},
                          "reasoning": "Mocking decision due to LLM unavailability."
                     }
                     # Example to break out of infinite wait
                     self.state.step_retry_count += 1
                     if self.state.step_retry_count > 1:
                          self.state.transition_to(FSMState.STEP_FAILED)
                          continue
                     
                console.print(f"  ├─ Action: {action_cmd.get('action_type')} | Reason: {action_cmd.get('reasoning')}")
                
                # Action Execution
                self.executor.execute(action_cmd)
                
                # Log Action
                self.action_log.log_action(self.session_id, self.state.task_id, self.state.current_step_id, action_cmd, screen_hash)
                
                # Validation (simplified: move to next step immediately for this mock structure)
                # In full system, we re-capture and check success criteria via LLM.
                time.sleep(1) # wait for action to settle
                console.print(f"  └─ Status: ✓ Step complete (Mocked validation)")
                
                if not self.state.advance_step():
                    # Task completed
                    break
                    
        except FailsafeTriggered:
            self.state.transition_to(FSMState.ABORTED)
            console.print("\n[bold red]\[ABORTED][/bold red] Failsafe triggered by user. Task stopped.")
        except Exception as e:
            logging.error(f"Task execution failed: {e}")
            self.state.transition_to(FSMState.FAILED)
            console.print(f"\n[bold red]\[ERROR][/bold red] {e}")
            
        finally:
            self.task_store.update_task_status(self.state.task_id, self.state.fsm_state.name)
            self.capture.task_complete(self.session_id)
            if self.state.fsm_state == FSMState.TASK_COMPLETE:
                 console.print(f"\n[bold green]\[COMPLETE][/bold green] Task finished successfully.")

    def _shutdown(self):
        console.print("[yellow]Cleaning up processes...[/yellow]")
        failsafe.stop()
        self.capture.shutdown()
        console.print("Goodbye.")
        
if __name__ == "__main__":
    app = LADAS()
    app.run_terminal_loop()
