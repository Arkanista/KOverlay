import sys
import os
import fcntl
import tempfile

# Force X11 backend (XWayland) to bypass strict Wayland limitations
# on absolute window positioning and transparent click-through inputs.
os.environ["QT_QPA_PLATFORM"] = "xcb"

lock_file_path = os.path.join(tempfile.gettempdir(), 'koverlay.lock')
lock_file = open(lock_file_path, 'w')
try:
    fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("KOverlay is already running. Exiting.")
    sys.exit(0)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import config
from settings_window import SettingsWindow
from ts3_client import TS3ClientThread
from overlay_window import OverlayWindow
from tray_icon import TrayIcon
from window_tracker import WindowTracker

class MainApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._execute_hide)
        from PyQt6.QtGui import QIcon
        self.app.setWindowIcon(QIcon("icon.svg"))
        
        # Load config
        self.cfg = config.load_config()
        
        # Migrate legacy config to overlay_ids dictionary
        if "overlay_ids" not in self.cfg:
            self.cfg["overlay_ids"] = {}
            primary_screen = self.app.primaryScreen()
            
            # Map existing monitors config if available
            if "monitors" in self.cfg:
                for i, screen in enumerate(self.app.screens(), start=1):
                    s_name = screen.name()
                    if s_name in self.cfg["monitors"]:
                        self.cfg["overlay_ids"][str(i)] = self.cfg["monitors"][s_name]
            else:
                # Default for primary
                self.cfg["overlay_ids"]["1"] = {
                    "enabled": True,
                    "pos_x": self.cfg.get("pos_x", 0),
                    "pos_y": self.cfg.get("pos_y", 0)
                }
            config.save_config(self.cfg)
        
        # Setup UI for multiple overlays
        self.overlays = {}
        for index in range(1, 5):
            overlay_id = str(index)
            mon_cfg = self.cfg["overlay_ids"].get(overlay_id, {})
            is_enabled = mon_cfg.get("enabled", False)
            if is_enabled:
                overlay = OverlayWindow(self.cfg, overlay_id, index)
                overlay.save_callback = self.save_config
                overlay.show()
                self.overlays[overlay_id] = overlay
        
        self.tray = TrayIcon(initial_mute=self.cfg.get("tts_muted", False))
        self.tray.show()
        
        # Connections
        self.tray.move_toggled.connect(self.on_move_toggled)
        self.tray.mute_toggled.connect(self.on_mute_toggled)
        self.tray.settings_requested.connect(self.show_settings)
        self.tray.quit_requested.connect(self.quit)
        
        # TS3 Client
        self.ts3_thread = TS3ClientThread(self.cfg.get("api_key", ""))
        self.ts3_thread.clients_updated.connect(self.on_clients_updated)
        self.ts3_thread.error_occurred.connect(self.on_ts3_error)
        self.ts3_thread.start()
        
        # Window Tracker (for kdotool/EVE focus)
        self.tracker = WindowTracker(
            target_keywords=self.cfg.get("target_keywords", ["EVE - ", "exefile.exe"]),
            polling_interval_ms=self.cfg.get("polling_interval_ms", 50)
        )
        self.tracker.active_window_changed.connect(self.on_active_window_changed)
        self.tracker.start()
        
        for overlay in self.overlays.values():
            overlay.blink_finished.connect(self.on_blink_finished)
        
        # Check if API key is missing
        if not self.cfg.get("api_key"):
            self.show_settings()
            
        # Start the blink effect requested by the user
        if not self.cfg.get("disable_blink", False):
            for overlay in self.overlays.values():
                overlay.start_blink()

    def on_clients_updated(self, clients, my_cid=None):
        for overlay in self.overlays.values():
            overlay.update_clients(clients, my_cid)

    def on_move_toggled(self, enabled):
        for overlay in self.overlays.values():
            overlay.set_move_mode(enabled)

    def on_mute_toggled(self, is_muted):
        self.cfg["tts_muted"] = is_muted
        self.save_config()

    def on_blink_finished(self):
        self.on_active_window_changed(self.tracker.last_state)

    def save_config(self):
        config.save_config(self.cfg)

    def show_settings(self):
        if hasattr(self, 'settings_dialog') and self.settings_dialog is not None:
            self.settings_dialog.activateWindow()
            return

        for overlay in self.overlays.values():
            overlay.set_move_mode(True)

        self.settings_dialog = SettingsWindow(self.cfg)
        self.settings_dialog.config_changed.connect(self.on_settings_changed)
        self.settings_dialog.finished.connect(self.on_settings_closed)
        self.settings_dialog.setModal(False)
        self.settings_dialog.show()

    def on_settings_changed(self):
        config.save_config(self.cfg)
        
        # Add or remove overlays based on checkboxes
        for index in range(1, 5):
            overlay_id = str(index)
            is_enabled = self.cfg["overlay_ids"].get(overlay_id, {}).get("enabled", False)
            
            if is_enabled and overlay_id not in self.overlays:
                overlay = OverlayWindow(self.cfg, overlay_id, index)
                overlay.save_callback = self.save_config
                overlay.blink_finished.connect(self.on_blink_finished)
                overlay.set_move_mode(True) # since settings is open
                self.overlays[overlay_id] = overlay
                
            elif not is_enabled and overlay_id in self.overlays:
                overlay = self.overlays[overlay_id]
                overlay.hide()
                overlay.deleteLater()
                del self.overlays[overlay_id]
                
        # Update styling for all active overlays
        for overlay in self.overlays.values():
            overlay.update_style()
            
        # Update WindowTracker keywords and polling interval
        new_keywords = self.cfg.get("target_keywords", ["EVE - ", "exefile.exe"])
        if self.tracker.target_keywords != new_keywords:
            self.tracker.target_keywords = new_keywords
            
        new_interval = self.cfg.get("polling_interval_ms", 50)
        if hasattr(self.tracker, 'polling_interval_ms') and self.tracker.polling_interval_ms != new_interval:
            self.tracker.polling_interval_ms = new_interval
        
        # Check if API key changed
        if self.ts3_thread.api_key != self.cfg.get("api_key", ""):
            self.ts3_thread.stop()
            self.ts3_thread = TS3ClientThread(self.cfg.get("api_key", ""))
            self.ts3_thread.clients_updated.connect(self.on_clients_updated)
            self.ts3_thread.error_occurred.connect(self.on_ts3_error)
            self.ts3_thread.start()
        
    def on_settings_closed(self):
        self.settings_dialog = None
        for overlay in self.overlays.values():
            overlay.set_move_mode(False)

    def on_active_window_changed(self, is_target_active):
        game_only = self.cfg.get("game_only", True)
        should_show = not game_only or is_target_active
        
        force_show = False
        if hasattr(self, 'settings_dialog') and self.settings_dialog is not None:
            force_show = True
            
        for overlay in self.overlays.values():
            if getattr(overlay, 'move_mode', False) or getattr(overlay, 'is_blinking', False):
                force_show = True
                
        if force_show or should_show:
            self.hide_timer.stop()
            for overlay in self.overlays.values():
                overlay.show()
        else:
            if self.cfg.get("hide_delay_enabled", False):
                if not self.hide_timer.isActive():
                    self.hide_timer.start(int(self.cfg.get("hide_delay_seconds", 5) * 1000))
            else:
                self._execute_hide()

    def _execute_hide(self):
        for overlay in self.overlays.values():
            if getattr(overlay, 'move_mode', False) or getattr(overlay, 'is_blinking', False):
                continue
            if hasattr(self, 'settings_dialog') and self.settings_dialog is not None:
                continue
            overlay.hide()
            
    def on_ts3_error(self, err_msg):
        # Just print for now, maybe add tray notification later
        print(err_msg)

    def quit(self):
        self.ts3_thread.stop()
        self.tracker.stop()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    import signal
    # This allows Ctrl+C in terminal to kill the Qt app gracefully without a core dump
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        app = MainApp()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
