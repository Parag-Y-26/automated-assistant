import threading
import time
import sys
import pyautogui
from pynput import keyboard

class FailsafeTriggered(Exception):
    """Exception raised when the failsafe key is pressed."""
    pass

class FailsafeMonitor:
    def __init__(self, failsafe_key="F12"):
        self.failsafe_key = failsafe_key
        self.triggered = False
        self._listener = None
        self._key_map = {
            "F12": keyboard.Key.f12,
            "ESC": keyboard.Key.esc,
            "PAUSE": keyboard.Key.pause
        }
        self.target_key = self._key_map.get(str(self.failsafe_key).upper(), keyboard.Key.f12)
        
        # Enable pyautogui failsafe (moving mouse to corner aborts)
        pyautogui.FAILSAFE = True

    def _on_press(self, key):
        if key == self.target_key:
            self.triggered = True
            print(f"\n[ABORTED] Failsafe key ({self.failsafe_key}) triggered. All actions stopped.", file=sys.stderr)
            return False  # Stop listener

    def start(self):
        """Start listening for the failsafe key in the background."""
        if self._listener is None or not self._listener.running:
            self.triggered = False
            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.start()

    def stop(self):
        """Stop listening for the failsafe key."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def check(self):
        """Check if the failsafe was triggered. Raises an exception if so."""
        if self.triggered:
            raise FailsafeTriggered("User aborted task via failsafe.")

# Global instance
failsafe = FailsafeMonitor()
