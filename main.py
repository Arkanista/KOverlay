import sys
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
        
        # Load config
        self.cfg = config.load_config()
        
        # Setup UI
        self.overlay = OverlayWindow(self.cfg)
        self.overlay.save_callback = self.save_config
        self.overlay.show()
        
        self.tray = TrayIcon()
        self.tray.show()
        
        # Connections
        self.tray.move_toggled.connect(self.overlay.set_move_mode)
        self.tray.settings_requested.connect(self.show_settings)
        self.tray.quit_requested.connect(self.quit)
        
        # TS3 Client
        self.ts3_thread = TS3ClientThread(self.cfg.get("api_key", ""))
        self.ts3_thread.clients_updated.connect(self.overlay.update_clients)
        self.ts3_thread.error_occurred.connect(self.on_ts3_error)
        self.ts3_thread.start()
        
        # Window Tracker (for kdotool/EVE focus)
        self.tracker = WindowTracker()
        self.tracker.active_window_changed.connect(self.on_active_window_changed)
        self.tracker.start()
        
        self.overlay.blink_finished.connect(self.on_blink_finished)
        
        # Check if API key is missing
        if not self.cfg.get("api_key"):
            self.show_settings()
            
        # Start the blink effect requested by the user
        self.overlay.start_blink()

    def on_blink_finished(self):
        self.on_active_window_changed(self.tracker.last_state)

    def save_config(self):
        config.save_config(self.cfg)

    def show_settings(self):
        dialog = SettingsWindow(self.cfg)
        if dialog.exec():
            new_cfg = dialog.get_updated_config()
            config.save_config(new_cfg)
            self.cfg = new_cfg
            
            # Restart TS3 thread with new key
            self.ts3_thread.stop()
            self.ts3_thread = TS3ClientThread(self.cfg.get("api_key", ""))
            self.ts3_thread.clients_updated.connect(self.overlay.update_clients)
            self.ts3_thread.error_occurred.connect(self.on_ts3_error)
            self.ts3_thread.start()
            
            self.overlay.config = self.cfg
            self.overlay.update_style()

    def on_active_window_changed(self, is_target_active):
        # If moving, always show.
        if self.overlay.move_mode:
            self.overlay.show()
            return
            
        if is_target_active:
            self.overlay.show()
        else:
            self.overlay.hide()
            
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
    try:
        app = MainApp()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
