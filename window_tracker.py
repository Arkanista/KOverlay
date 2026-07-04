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
        self.xdotool_missing = False
        self.active_tool = None

    def check_tools(self):
        try:
            subprocess.run(["kdotool", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.active_tool = "kdotool"
            return True
        except FileNotFoundError:
            self.kdotool_missing = True
            
        try:
            subprocess.run(["xdotool", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.active_tool = "xdotool"
            return True
        except FileNotFoundError:
            self.xdotool_missing = True
            
        print("Warning: Neither kdotool nor xdotool found. Active window tracking will be disabled (overlay always visible).")
        return False

    def run(self):
        tools_available = self.check_tools()
        
        while self.running:
            if not tools_available:
                # Fallback: always show
                if not self.last_state:
                    self.active_window_changed.emit(True)
                    self.last_state = True
                time.sleep(2.0)
                continue
                
            try:
                # getactivewindow returns the window ID, getwindowname gets the title of that ID
                result = subprocess.run(
                    [self.active_tool, "getactivewindow", "getwindowname"],
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
