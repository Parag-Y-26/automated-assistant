import asyncio
import logging
import subprocess
import os
from execution.keyboard_controller import KeyboardController
from execution.mouse_controller import MouseController
from execution.failsafe_monitor import failsafe
from tools.perplexity_search import PerplexitySearchTool

class ActionExecutor:
    def __init__(self, config: dict):
        self.exec_config = config.get("execution", {})
        self.keyboard = KeyboardController(
            min_delay_ms=self.exec_config.get("min_type_delay_ms", 30),
            max_delay_ms=self.exec_config.get("max_type_delay_ms", 80)
        )
        self.mouse = MouseController(
            cursor_speed_multiplier=self.exec_config.get("cursor_speed_multiplier", 1.0),
            drag_hold_delay_ms=self.exec_config.get("drag_hold_delay_ms", 150),
            drag_release_delay_ms=self.exec_config.get("drag_release_delay_ms", 100)
        )
        # Initialize Perplexity tool for Autonomous Web Retrieval
        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        self.perplexity = PerplexitySearchTool(api_key=api_key)

    async def execute(self, action_cmd: dict):
        """Asynchronously dispatches the action command JSON to the correct controller."""
        failsafe.check()
        if not isinstance(action_cmd, dict):
            raise ValueError(f"Action command must be a dict, got {type(action_cmd)}")
            
        action_type = action_cmd.get("action_type")
        if not action_type or not isinstance(action_type, str):
            raise ValueError("action_cmd missing required 'action_type' field (string)")
        coords = action_cmd.get("coordinates")
        params = action_cmd.get("parameters", {})
        
        if not isinstance(coords, dict):
            coords = None
        if not isinstance(params, dict):
            params = {}
        
        if not coords and "target" in params and isinstance(params["target"], dict) and "bbox" in params["target"]:
            bbox = params["target"]["bbox"]
            if len(bbox) == 4:
                coords = {
                    "x": bbox[0] + (bbox[2] - bbox[0]) / 2,
                    "y": bbox[1] + (bbox[3] - bbox[1]) / 2
                }
        
        pre_wait = action_cmd.get("pre_action_wait_ms", 0) / 1000.0
        post_wait = action_cmd.get("post_action_wait_ms", 0) / 1000.0
        
        if pre_wait > 0:
            await asyncio.sleep(pre_wait)
            
        x = coords.get("x") if coords else None
        y = coords.get("y") if coords else None

        pointer_actions = {"click", "double_click", "right_click", "move", "scroll"}
        if action_type in pointer_actions and (x is None or y is None):
            raise ValueError(f"Action '{action_type}' requires coordinates x/y (or a target bbox in parameters)")

        action_result = None

        try:
            if self.exec_config.get("dry_run", False):
                logging.info(f"DRY RUN: Executing {action_type} with coords {coords} and params {params}")
                if post_wait > 0:
                    await asyncio.sleep(post_wait)
                return None

            if action_type == "click":
                await asyncio.to_thread(self.mouse.click, x, y, button=params.get("button", "left"))
                
            elif action_type == "double_click":
                await asyncio.to_thread(self.mouse.double_click, x, y, button=params.get("button", "left"))
                
            elif action_type == "right_click":
                await asyncio.to_thread(self.mouse.click, x, y, button="right")
                
            elif action_type == "move":
                if x is not None and y is not None:
                     await asyncio.to_thread(self.mouse.move, x, y)
                     
            elif action_type == "drag":
                start = params.get("start_coords")
                end = params.get("end_coords")
                if start and end:
                    await asyncio.to_thread(self.mouse.drag, start["x"], start["y"], end["x"], end["y"])
                    
            elif action_type == "scroll":
                dy = params.get("amount", -1)
                await asyncio.to_thread(self.mouse.scroll, x, y, dy)
                
            elif action_type == "type_text":
                if x is not None and y is not None:
                    await asyncio.to_thread(self.mouse.click, x, y)
                text = params.get("text", "")
                if params.get("clear_first", False):
                    await asyncio.to_thread(self.keyboard.hotkey, "ctrl", "a")
                    await asyncio.to_thread(self.keyboard.press_key, "backspace")
                await asyncio.to_thread(self.keyboard.type_text, text)
                
            elif action_type == "press_key":
                await asyncio.to_thread(self.keyboard.press_key, params.get("key", "enter"))
                
            elif action_type == "hotkey":
                keys = params.get("keys", [])
                if keys:
                    hotkey_str = "+".join(keys).lower()
                    allowed_hotkeys = self.exec_config.get("allowed_hotkeys", [])
                    unsafe_mode = self.exec_config.get("unsafe_mode", False)
                    if not unsafe_mode and allowed_hotkeys and hotkey_str not in allowed_hotkeys:
                         raise PermissionError(f"Hotkey '{hotkey_str}' blocked by safety policy.")
                    await asyncio.to_thread(self.keyboard.hotkey, *keys)
                    
            elif action_type == "wait":
                wait_time = params.get("duration_ms", 1000) / 1000.0
                await asyncio.sleep(wait_time)
                
            elif action_type == "run_command":
                command = params.get("command", "")
                if not isinstance(command, str) or not command.strip():
                    raise ValueError("run_command requires non-empty parameters.command")
                is_allowed = any(command.startswith(cmd) for cmd in self.exec_config.get("allowed_commands", []))
                if not self.exec_config.get("unsafe_mode", False) and not is_allowed:
                    raise PermissionError(f"Command '{command}' blocked by safety policy.")
                logging.info(f"Running command: {command}")
                await asyncio.to_thread(subprocess.Popen, command, shell=True)
                
            elif action_type == "search_web":
                # Autonomous Web Retrieval
                query = params.get("query", "")
                logging.info(f"Autonomously searching web for: {query}")
                action_result = await self.perplexity.search(query)
                logging.info("Web search complete.")
                
            elif action_type == "screenshot":
                logging.info("Explicit screenshot requested by LLM.")
                
            else:
                logging.warning(f"Unknown async action type: {action_type}, treating as No-Op.")
                
        except Exception as e:
            logging.error(f"Action execute failed: {e}")
            raise
            
        if post_wait > 0:
            await asyncio.sleep(post_wait)
            
        return action_result
