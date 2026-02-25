import random
import time
from pynput.keyboard import Controller, Key
from execution.failsafe_monitor import failsafe

class KeyboardController:
    def __init__(self, min_delay_ms=30, max_delay_ms=80):
        self.keyboard = Controller()
        self.min_delay = min_delay_ms / 1000.0
        self.max_delay = max_delay_ms / 1000.0
        
        self.special_keys = {
            "enter": Key.enter,
            "tab": Key.tab,
            "esc": Key.esc,
            "space": Key.space,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "ctrl": Key.ctrl,
            "alt": Key.alt,
            "shift": Key.shift,
            "win": Key.cmd
        }

    def _human_delay(self):
        """Sleep for a random human-like delay between typing characters."""
        time.sleep(random.uniform(self.min_delay, self.max_delay))
        failsafe.check()

    def type_text(self, text: str):
        """Type a string character by character with delays."""
        for char in text:
            failsafe.check()
            self.keyboard.type(char)
            self._human_delay()

    def press_key(self, key_name: str):
        """Press and release a single key (can be special key or char)."""
        key = self.special_keys.get(key_name.lower(), key_name)
        self.keyboard.press(key)
        time.sleep(random.uniform(0.02, 0.08)) # Short hold
        self.keyboard.release(key)
        self._human_delay()

    def hold_key(self, key_name: str):
        """Hold a key down."""
        key = self.special_keys.get(key_name.lower(), key_name)
        self.keyboard.press(key)

    def release_key(self, key_name: str):
        """Release a held key."""
        key = self.special_keys.get(key_name.lower(), key_name)
        self.keyboard.release(key)

    def hotkey(self, *keys_names):
        """Press a combination of keys (e.g., 'ctrl', 'c')."""
        keys = [self.special_keys.get(k.lower(), k) for k in keys_names]
        
        # Press all down
        for key in keys:
            self.keyboard.press(key)
            time.sleep(random.uniform(0.01, 0.03))
            
        time.sleep(random.uniform(0.05, 0.1))
        
        # Release all in reverse order
        for key in reversed(keys):
            self.keyboard.release(key)
            time.sleep(random.uniform(0.01, 0.03))
            
        self._human_delay()
