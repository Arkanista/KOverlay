import sys
import os
import subprocess
import time
from PyQt6.QtCore import QThread, pyqtSignal

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

class WindowTracker(QThread):
    active_window_changed = pyqtSignal(bool)

    def __init__(self, target_keywords=None, polling_interval_ms=50, parent=None):
        super().__init__(parent)
        # Usually EVE Online window contains "EVE - " or "exefile.exe"
        self.target_keywords = target_keywords or ["EVE - ", "exefile.exe"]
        self.polling_interval_ms = polling_interval_ms
        self.running = True
        self.last_state = True
        self.kdotool_missing = False
        self.xdotool_missing = False
        self.active_tool = None

    def check_tools(self):
        if sys.platform == "win32":
            self.active_tool = "win32"
            return True

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

    def _get_active_window_info_win32(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value

            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe_name = ""
            if pid.value:
                # 0x1000 = PROCESS_QUERY_LIMITED_INFORMATION
                h_proc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
                if h_proc:
                    try:
                        exe_buf = ctypes.create_unicode_buffer(1024)
                        size = wintypes.DWORD(1024)
                        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_proc, 0, exe_buf, ctypes.byref(size)):
                            exe_name = os.path.basename(exe_buf.value)
                    finally:
                        ctypes.windll.kernel32.CloseHandle(h_proc)
            return f"{title} {exe_name}".strip()
        except Exception:
            return ""

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
                
            is_active = False
            try:
                if self.active_tool == "win32":
                    window_info = self._get_active_window_info_win32()
                    for kw in self.target_keywords:
                        if kw.lower() in window_info.lower():
                            is_active = True
                            break
                else:
                    # getactivewindow returns the window ID, getwindowname gets the title of that ID
                    result = subprocess.run(
                        [self.active_tool, "getactivewindow", "getwindowname"],
                        capture_output=True, text=True, timeout=0.5
                    )
                    if result.returncode == 0:
                        window_name = result.stdout.strip()
                        for kw in self.target_keywords:
                            if kw.lower() in window_name.lower():
                                is_active = True
                                break
            except Exception as e:
                # On timeout or broken display server after suspend, assume not active
                pass
                
            if is_active != self.last_state:
                self.active_window_changed.emit(is_active)
                self.last_state = is_active
                
            # Safely get interval in seconds, fallback to 50ms if missing or invalid
            interval_sec = getattr(self, 'polling_interval_ms', 50) / 1000.0
            time.sleep(interval_sec)

    def stop(self):
        self.running = False
        self.wait()
