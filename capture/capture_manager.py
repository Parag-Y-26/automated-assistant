import os
import time
import imagehash
from PIL import Image
from capture.screen_capture import ScreenCapture
from capture.cleanup import CaptureCleanup

class CaptureManager:
    """Orchestrates screen capture, cleanup, and loop detection via caching."""
    def __init__(self, config: dict):
        self.config = config.get("capture", {})
        self.temp_dir = os.path.join(os.getcwd(), "temp_screens")
        
        monitor_index = self.config.get("monitor_index", 0)
        self.screen_capture = ScreenCapture(monitor_index=monitor_index)
        
        self.cleanup = CaptureCleanup(
            temp_dir=self.temp_dir,
            max_count=self.config.get("max_screenshot_count", 200),
            max_age_seconds=self.config.get("max_retention_seconds", 3600)
        )
        
        # Start background cleanup every 60s
        self.cleanup.start_background_cleanup(interval_seconds=60)
        
        self.last_capture_path = None
        self.last_hash = None
        
    def capture_screen(self, session_id: str, step_id: str) -> dict:
        """
        Capture the current screen. 
        Returns dict containing the file path and perceptual hash.
        """
        timestamp = int(time.time() * 1000)
        filename = f"{session_id}_{timestamp}_{step_id}.png"
        output_path = os.path.join(self.temp_dir, filename)
        
        region = self.config.get("capture_region", None)
        
        if region:
            self.screen_capture.capture_region(region, output_path)
        else:
            self.screen_capture.capture_full_screen(output_path)
            
        self.last_capture_path = output_path
        
        # Compute phash for loop detection
        try:
            img = Image.open(output_path)
            self.last_hash = str(imagehash.phash(img))
        except Exception:
            self.last_hash = None
            
        return {
            "path": output_path,
            "hash": self.last_hash,
            "timestamp": timestamp
        }
        
    def get_monitor_dimensions(self):
        return self.screen_capture.get_monitor_dimensions()
        
    def check_loop(self, new_hash: str) -> bool:
        """Return True if the new hash exactly matches the last hash."""
        if not new_hash or not self.last_hash:
            return False
        return new_hash == self.last_hash
        
    def task_complete(self, session_id: str):
        """Called when a task is finished to clean up all its screens immediately."""
        self.cleanup.clean_session(session_id)
        self.cleanup.enforce_policy()
        
    def shutdown(self):
        self.cleanup.stop_background_cleanup()
        self.screen_capture.close()
