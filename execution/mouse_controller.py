import time
import random
from pynput.mouse import Controller, Button
from execution.motion_animator import MotionAnimator
from execution.failsafe_monitor import failsafe

class MouseController:
    def __init__(self, 
                 cursor_speed_multiplier=1.0,
                 drag_hold_delay_ms=150,
                 drag_release_delay_ms=100):
        
        self.mouse = Controller()
        self.animator = MotionAnimator(cursor_speed_multiplier=cursor_speed_multiplier)
        self.drag_hold_delay = drag_hold_delay_ms / 1000.0
        self.drag_release_delay = drag_release_delay_ms / 1000.0

    def _get_button(self, btn_name: str) -> Button:
        if btn_name.lower() in ["right", "r"]:
            return Button.right
        elif btn_name.lower() in ["middle", "m"]:
            return Button.middle
        return Button.left

    def get_position(self) -> tuple[int, int]:
        return self.mouse.position

    def move(self, x: int, y: int):
        """Move cursor smoothly to (x, y)."""
        failsafe.check()
        current_pos = self.mouse.position
        self.animator.move_mouse(current_pos, (x, y), self.mouse)

    def click(self, x: int = None, y: int = None, button: str = "left"):
        """Move to (x,y) if provided, then click."""
        if x is not None and y is not None:
            self.move(x, y)
            
        failsafe.check()
        btn = self._get_button(button)
        
        self.mouse.press(btn)
        time.sleep(random.uniform(0.04, 0.09)) # human click duration
        self.mouse.release(btn)
        
        time.sleep(random.uniform(0.1, 0.3)) # post-click pause

    def double_click(self, x: int = None, y: int = None, button: str = "left"):
        """Move to (x,y) if provided, then double click."""
        if x is not None and y is not None:
            self.move(x, y)
            
        failsafe.check()
        btn = self._get_button(button)
        
        # Click 1
        self.mouse.press(btn)
        time.sleep(random.uniform(0.03, 0.07))
        self.mouse.release(btn)
        
        # Between clicks
        time.sleep(random.uniform(0.04, 0.09))
        
        # Click 2
        self.mouse.press(btn)
        time.sleep(random.uniform(0.03, 0.07))
        self.mouse.release(btn)
        
        time.sleep(random.uniform(0.1, 0.3))

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int):
        """Click and hold at start, drag smoothly to end, release."""
        failsafe.check()
        
        # Move to start
        self.move(start_x, start_y)
        
        # Press and hold
        self.mouse.press(Button.left)
        time.sleep(self.drag_hold_delay + random.uniform(0, 0.1))
        
        # Drag smoothly
        self.animator.move_mouse((start_x, start_y), (end_x, end_y), self.mouse)
        
        # Pause before release
        time.sleep(self.drag_release_delay + random.uniform(0, 0.05))
        
        # Release
        self.mouse.release(Button.left)
        time.sleep(random.uniform(0.2, 0.4))

    def scroll(self, x: int = None, y: int = None, dy: int = -1):
        """Move to (x,y) if provided, then scroll (dy < 0 is down, dy > 0 is up)."""
        if x is not None and y is not None:
            self.move(x, y)
            
        failsafe.check()
        self.mouse.scroll(0, dy)
        time.sleep(random.uniform(0.2, 0.5))

    def hover(self, x: int, y: int):
        """Move to (x,y) and pause."""
        self.move(x, y)
        time.sleep(random.uniform(0.5, 1.0)) # Wait slightly longer for hover effects
