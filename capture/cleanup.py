import os
import time
import glob
import logging
import threading

class CaptureCleanup:
    def __init__(self, temp_dir: str, max_count: int = 200, max_age_seconds: int = 3600):
        self.temp_dir = temp_dir
        self.max_count = max_count
        self.max_age_seconds = max_age_seconds
        
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
            
        self._stop_event = threading.Event()
        self._thread = None

    def clean_session(self, session_id: str):
        """Delete all screenshots belonging to a specific session."""
        pattern = os.path.join(self.temp_dir, f"{session_id}_*.png")
        files = glob.glob(pattern)
        for f in files:
            try:
                os.remove(f)
            except OSError as e:
                logging.warning(f"Could not remove temporary screenshot {f}: {e}")
        logging.info(f"Cleaned {len(files)} screenshots for session {session_id}")

    def enforce_policy(self):
        """Enforce the max_count and max_age_seconds policies."""
        try:
            files = [os.path.join(self.temp_dir, f) for f in os.listdir(self.temp_dir) if f.endswith('.png')]
        except FileNotFoundError:
            return

        now = time.time()
        
        # 1. Enforce max age
        files_removed = 0
        valid_files = []
        for f in files:
            try:
                mtime = os.path.getmtime(f)
                if now - mtime > self.max_age_seconds:
                    os.remove(f)
                    files_removed += 1
                else:
                    valid_files.append((mtime, f))
            except OSError:
                continue
                
        # 2. Enforce max count (remove oldest first)
        if len(valid_files) > self.max_count:
            # Sort by mtime ascending
            valid_files.sort(key=lambda x: x[0])
            to_remove_count = len(valid_files) - self.max_count
            for i in range(to_remove_count):
                try:
                    os.remove(valid_files[i][1])
                    files_removed += 1
                except OSError:
                    continue
                    
        if files_removed > 0:
            logging.info(f"Retention policy enforced: removed {files_removed} old/excess screenshots.")

    def _cleanup_loop(self, interval_seconds: int = 60):
        """Background loop to periodically enforce the policy."""
        while not self._stop_event.is_set():
            self.enforce_policy()
            # Wait for interval or stop event
            self._stop_event.wait(interval_seconds)

    def start_background_cleanup(self, interval_seconds: int = 60):
        """Start the background cleanup thread."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._cleanup_loop, 
                args=(interval_seconds,),
                daemon=True,
                name="CaptureCleanupThread"
            )
            self._thread.start()

    def stop_background_cleanup(self):
        """Stop the background cleanup thread."""
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=2.0)
            self._thread = None
