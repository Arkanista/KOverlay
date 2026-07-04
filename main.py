import sys
import os

# Force X11 backend (XWayland) to bypass strict Wayland limitations
# on absolute window positioning and transparent click-through inputs.
os.environ["QT_QPA_PLATFORM"] = "xcb"

from PyQt6.QtWidgets import QApplication
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
        
        self.tray = TrayIcon()
        self.tray.show()
        
        # Connections
        self.tray.move_toggled.connect(self.on_move_toggled)
        self.tray.settings_requested.connect(self.show_settings)
        self.tray.quit_requested.connect(self.quit)
        
        # TS3 Client
        self.ts3_thread = TS3ClientThread(self.cfg.get("api_key", ""))
        self.ts3_thread.clients_updated.connect(self.on_clients_updated)
        self.ts3_thread.error_occurred.connect(self.on_ts3_error)
        self.ts3_thread.start()
        
        # Window Tracker (for kdotool/EVE focus)
        self.tracker = WindowTracker()
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

    def on_clients_updated(self, clients):
        for overlay in self.overlays.values():
            overlay.update_clients(clients)

    def on_move_toggled(self, enabled):
        for overlay in self.overlays.values():
            overlay.set_move_mode(enabled)

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
        for overlay in self.overlays.values():
            # If moving, always show.
            if getattr(overlay, 'move_mode', False) or getattr(overlay, 'is_blinking', False):
                overlay.show()
                continue
                
            if hasattr(self, 'settings_dialog') and self.settings_dialog is not None:
                overlay.show()
                continue
                
            game_only = self.cfg.get("game_only", True)
            if not game_only or is_target_active:
                overlay.show()
            else:
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
