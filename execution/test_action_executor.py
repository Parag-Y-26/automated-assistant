import unittest
import sys
from unittest.mock import MagicMock

sys.modules['pynput'] = MagicMock()
sys.modules['pynput.keyboard'] = MagicMock()
sys.modules['pynput.mouse'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['pywin32'] = MagicMock() # just in case

from execution.action_executor import ActionExecutor
from execution.action_executor import ActionExecutor

class TestActionExecutor(unittest.TestCase):
    def setUp(self):
        self.config = {
            "execution": {
                "dry_run": False,
                "unsafe_mode": False,
                "allowed_commands": ["calc.exe", "notepad"],
                "allowed_hotkeys": ["ctrl+c", "alt+tab"]
            }
        }
        self.executor = ActionExecutor(self.config)
        self.executor.mouse = MagicMock()
        self.executor.keyboard = MagicMock()

    def test_dry_run_bypasses_os_calls(self):
        self.config["execution"]["dry_run"] = True
        executor = ActionExecutor(self.config)
        executor.mouse = MagicMock()
        
        executor.execute({"action_type": "click", "coordinates": {"x": 100, "y": 100}})
        executor.mouse.click.assert_not_called()

    def test_target_resolution(self):
        # Target bounding box: [100, 200, 300, 400]
        # Center should be x=200, y=300
        cmd = {
            "action_type": "click",
            "parameters": {
                "target": {"bbox": [100, 200, 300, 400]}
            }
        }
        self.executor.execute(cmd)
        self.executor.mouse.click.assert_called_once_with(200.0, 300.0, button='left')
        
    def test_blocked_command_raises_permission_error(self):
        cmd = {
            "action_type": "run_command",
            "parameters": {"command": "format C:"}
        }
        with self.assertRaises(PermissionError):
            self.executor.execute(cmd)
            
    def test_allowed_command_executes(self):
        cmd = {
            "action_type": "run_command",
            "parameters": {"command": "calc.exe"}
        }
        # In actual test, we'd mock subprocess.Popen
        # For simplicity, just asserting no PermissionError is raised
        # (Though it will try to actually run calc.exe locally, so let's mock subprocess)
        import subprocess
        with unittest.mock.patch('subprocess.Popen') as mock_popen:
            self.executor.execute(cmd)
            mock_popen.assert_called_once()
            
    def test_hotkey_safety(self):
        # allowed
        self.executor.execute({"action_type": "hotkey", "parameters": {"keys": ["ctrl", "c"]}})
        self.executor.keyboard.hotkey.assert_called_with("ctrl", "c")
        
        # blocked
        with self.assertRaises(PermissionError):
            self.executor.execute({"action_type": "hotkey", "parameters": {"keys": ["ctrl", "alt", "delete"]}})

if __name__ == '__main__':
    unittest.main()
