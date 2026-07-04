import subprocess
import time
from PyQt6.QtCore import QThread, pyqtSignal

class WindowTracker(QThread):
    active_window_changed = pyqtSignal(bool)

    def __init__(self, target_keywords=None, parent=None):
        super().__init__(parent)
        # Usually EVE Online window contains "EVE"
        self.target_keywords = target_keywords or ["EVE", "EVE Online"]
        self.running = True
        self.last_state = True
        self.kdotool_missing = False

    def check_kdotool(self):
        try:
            subprocess.run(["kdotool", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            print("Warning: kdotool not found. Active window tracking will be disabled (overlay always visible).")
            return False

    def run(self):
        self.kdotool_missing = not self.check_kdotool()
        
        while self.running:
            if self.kdotool_missing:
                # Fallback: always show
                if not self.last_state:
                    self.active_window_changed.emit(True)
                    self.last_state = True
                time.sleep(2.0)
                continue
                
            try:
                # getactivewindow returns the window ID, getwindowname gets the title of that ID
                # Actually, "kdotool getactivewindow getwindowname" works in sequence
                result = subprocess.run(
                    ["kdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=1.0
                )
                window_name = result.stdout.strip()
                
                is_active = False
                for kw in self.target_keywords:
                    if kw.lower() in window_name.lower():
                        is_active = True
                        break
                        
                if is_active != self.last_state:
                    self.active_window_changed.emit(is_active)
                    self.last_state = is_active
                    
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                print(f"Error tracking window: {e}")
                
            time.sleep(1.0) # Check every 1 second

    def stop(self):
        self.running = False
        self.wait()
