import time
import logging
from execution.keyboard_controller import KeyboardController
from execution.mouse_controller import MouseController

class ActionExecutor:
    def __init__(self, config: dict):
        exec_config = config.get("execution", {})
        self.keyboard = KeyboardController(
            min_delay_ms=exec_config.get("min_type_delay_ms", 30),
            max_delay_ms=exec_config.get("max_type_delay_ms", 80)
        )
        self.mouse = MouseController(
            cursor_speed_multiplier=exec_config.get("cursor_speed_multiplier", 1.0),
            drag_hold_delay_ms=exec_config.get("drag_hold_delay_ms", 150),
            drag_release_delay_ms=exec_config.get("drag_release_delay_ms", 100)
        )

    def execute(self, action_cmd: dict):
        """Dispatches the action command JSON to the correct controller."""
        action_type = action_cmd.get("action_type")
        coords = action_cmd.get("coordinates")
        params = action_cmd.get("parameters", {})
        
        pre_wait = action_cmd.get("pre_action_wait_ms", 0) / 1000.0
        post_wait = action_cmd.get("post_action_wait_ms", 0) / 1000.0
        
        if pre_wait > 0:
            time.sleep(pre_wait)
            
        x = coords.get("x") if coords else None
        y = coords.get("y") if coords else None

        try:
            if action_type == "click":
                self.mouse.click(x, y, button=params.get("button", "left"))
                
            elif action_type == "double_click":
                self.mouse.double_click(x, y, button=params.get("button", "left"))
                
            elif action_type == "right_click":
                self.mouse.click(x, y, button="right")
                
            elif action_type == "move":
                if x is not None and y is not None:
                     self.mouse.move(x, y)
                     
            elif action_type == "drag":
                start = params.get("start_coords")
                end = params.get("end_coords")
                if start and end:
                    self.mouse.drag(start["x"], start["y"], end["x"], end["y"])
                    
            elif action_type == "scroll":
                dy = params.get("amount", -1)
                self.mouse.scroll(x, y, dy)
                
            elif action_type == "type_text":
                # If coords provided, click first to focus
                if x is not None and y is not None:
                    self.mouse.click(x, y)
                text = params.get("text", "")
                if params.get("clear_first", False):
                    # Basic clear: ctrl+a, backspace
                    self.keyboard.hotkey("ctrl", "a")
                    self.keyboard.press_key("backspace")
                self.keyboard.type_text(text)
                
            elif action_type == "press_key":
                self.keyboard.press_key(params.get("key", "enter"))
                
            elif action_type == "hotkey":
                keys = params.get("keys", [])
                if keys:
                    self.keyboard.hotkey(*keys)
                    
            elif action_type == "wait":
                wait_time = params.get("duration_ms", 1000) / 1000.0
                time.sleep(wait_time)
                
            else:
                logging.warning(f"Unknown action type: {action_type}")
                
        except Exception as e:
            logging.error(f"Action execution failed: {e}")
            raise
            
        if post_wait > 0:
            time.sleep(post_wait)
