import sys
import os
import tempfile
import ctypes
import traceback
import time

# Ensure application root directory is always on sys.path (critical for Python embeddable)
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Global exception hook to show GUI dialog and write log on unexpected crash
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        log_dir = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "koverlay")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "crash.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- Crash at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            f.write(err_msg)
    except Exception:
        log_path = "crash.log"

    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"An error occurred while running KOverlay:\n\n{err_msg}\nDetails saved to:\n{log_path}",
                "KOverlay - Error",
                0x10
            )
        except Exception:
            pass
    print(err_msg, file=sys.stderr)

sys.excepthook = handle_exception

if sys.platform != "win32":
    try:
        # Set the process name to 'koverlay' for htop/ps/killall
        libc = ctypes.cdll.LoadLibrary('libc.so.6')
        libc.prctl(15, b'koverlay', 0, 0, 0)
    except Exception:
        pass

    # Force X11 backend (XWayland) to bypass strict Wayland limitations
    # on absolute window positioning and transparent click-through inputs.
    os.environ["QT_QPA_PLATFORM"] = "xcb"

def show_already_running_message():
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                "KOverlay is already running and active in the system tray (near the clock in the notification area).\n\nRight-click the KOverlay tray icon to open Settings.",
                "KOverlay",
                0x40  # MB_ICONINFORMATION
            )
        except Exception:
            pass
    print("KOverlay is already running. Exiting.")

lock_file_path = os.path.join(tempfile.gettempdir(), 'koverlay.lock')
lock_file = open(lock_file_path, 'w')
try:
    # Ensure single instance
    from PyQt6.QtCore import QSharedMemory
    shared_memory = QSharedMemory("KOverlay_TS3_Instance")
    if shared_memory.attach():
        shared_memory.detach()
        
    if not shared_memory.create(1):
        show_already_running_message()
        sys.exit(0)

    if sys.platform != "win32":
        import fcntl
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        import msvcrt
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except (IOError, OSError):
    show_already_running_message()
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

        # Apply system theme (Dark/Light on Windows, native on Linux)
        import theme_manager
        theme_manager.apply_app_theme(self.app)

        if sys.platform == "win32":
            self.theme_timer = QTimer(self.app)
            self.theme_timer.timeout.connect(self._check_system_theme)
            self.theme_timer.start(2500)

        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._execute_hide)
        
        from PyQt6.QtGui import QIcon
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.app.setWindowIcon(QIcon(icon_path))
        
        # Load config
        self.first_run = not os.path.exists(config.CONFIG_FILE)
        self.cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.cfg = config.load_config()
        
        # Initialize TTS Manager early to start the worker thread
        from tts_manager import get_tts_manager
        get_tts_manager(self.cfg)
        
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
                # Default for primary - center on the primary screen
                if primary_screen:
                    geom = primary_screen.geometry()
                    default_x = geom.x() + (geom.width() - 200) // 2
                    default_y = geom.y() + (geom.height() - 100) // 2
                else:
                    default_x = 0
                    default_y = 0
                self.cfg["overlay_ids"]["1"] = {
                    "enabled": True,
                    "pos_x": self.cfg.get("pos_x", default_x),
                    "pos_y": self.cfg.get("pos_y", default_y)
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
        
        self.tray = TrayIcon(
            initial_mute=self.cfg.get("tts_muted", False),
            overlays_config=self.cfg.get("overlay_ids", {}),
            initial_platform=self.cfg.get("voice_backend", "ts3")
        )
        self.tray.show()

        # Show notification so user knows KOverlay is running in system tray
        self.tray.showMessage(
            "KOverlay",
            "KOverlay is running in the system tray.\nIMPORTANT: KOverlay must remain running for the overlay to appear!\nRight-click tray icon to open Settings.",
            self.tray.MessageIcon.Information,
            5000
        )

        if self.first_run:
            QTimer.singleShot(600, self.show_settings)

        # Connections
        self.tray.move_toggled.connect(self.on_move_toggled)
        self.tray.mute_toggled.connect(self.on_mute_toggled)
        self.tray.overlay_toggled.connect(self.on_tray_overlay_toggled)
        self.tray.platform_changed.connect(self.on_platform_changed)
        self.tray.settings_requested.connect(self.show_settings)
        self.tray.quit_requested.connect(self.quit)
        
        # Voice Client Backend (TS3 or Mumble)
        self.voice_thread = None
        self.start_voice_backend()
        
        # Window Tracker (for kdotool/EVE focus)
        self.tracker = WindowTracker(
            target_keywords=self.cfg.get("target_keywords", ["EVE - ", "exefile.exe"]),
            polling_interval_ms=self.cfg.get("polling_interval_ms", 50)
        )
        self.tracker.active_window_changed.connect(self.on_active_window_changed)
        self.tracker.start()
        
        for overlay in self.overlays.values():
            overlay.blink_finished.connect(self.on_blink_finished)
        
        # Check if API key is missing (only for TS3 backend)
        if self.cfg.get("voice_backend", "ts3") == "ts3" and not self.cfg.get("api_key"):
            self.show_settings()
            
        # Start the blink effect requested by the user
        if not self.cfg.get("disable_blink", False):
            for overlay in self.overlays.values():
                overlay.start_blink()

    def on_clients_updated(self, clients, my_cid=None):
        first = True
        for overlay in self.overlays.values():
            overlay.is_primary = first
            first = False
            overlay.update_clients(clients, my_cid)

    def on_move_toggled(self, enabled):
        for overlay in self.overlays.values():
            overlay.set_move_mode(enabled)
            
        # Force visibility sync after exiting move mode
        if not enabled and hasattr(self, 'tracker') and hasattr(self.tracker, 'last_state'):
            self.on_active_window_changed(self.tracker.last_state)

    def on_mute_toggled(self, is_muted):
        self.cfg["tts_muted"] = is_muted
        self.save_config()

    def on_tray_overlay_toggled(self, overlay_id, is_enabled):
        if overlay_id not in self.cfg["overlay_ids"]:
            self.cfg["overlay_ids"][overlay_id] = {}
        self.cfg["overlay_ids"][overlay_id]["enabled"] = is_enabled
        self.save_config()
        self.on_settings_changed()

    def on_platform_changed(self, platform):
        if self.cfg.get("voice_backend", "ts3") == platform:
            return
        self.cfg["voice_backend"] = platform
        self.save_config()
        self.tray.set_active_platform(platform)
        if hasattr(self, 'settings_dialog') and self.settings_dialog is not None:
            self.settings_dialog.set_active_platform(platform)
        self.start_voice_backend()

    def on_blink_finished(self):
        self.on_active_window_changed(self.tracker.last_state)

    def save_config(self):
        config.save_config(self.cfg)

    def _check_system_theme(self):
        windows = []
        if hasattr(self, 'settings_dialog') and self.settings_dialog is not None:
            windows.append(self.settings_dialog)
        import theme_manager
        theme_manager.check_and_update_theme(self.app, windows)

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

        import theme_manager
        theme_manager.apply_window_theme(self.settings_dialog)

    def on_settings_changed(self):
        config.save_config(self.cfg)
        
        # Add or remove overlays based on checkboxes
        for index in range(1, 5):
            overlay_id = str(index)
            is_enabled = self.cfg["overlay_ids"].get(overlay_id, {}).get("enabled", False)
            
            # Keep tray icon in sync
            self.tray.update_overlay_state(overlay_id, is_enabled)
            
            if is_enabled and overlay_id not in self.overlays:
                overlay = OverlayWindow(self.cfg, overlay_id, index)
                overlay.save_callback = self.save_config
                overlay.blink_finished.connect(self.on_blink_finished)
                is_settings_open = hasattr(self, 'settings_dialog') and self.settings_dialog is not None
                is_move_toggled = self.tray.move_action.isChecked()
                overlay.set_move_mode(is_settings_open or is_move_toggled)
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

        # Check if voice backend or its connection settings changed
        backend = self.cfg.get("voice_backend", "ts3")
        self.tray.set_active_platform(backend)
        need_restart = False
        if getattr(self, 'voice_backend', None) != backend:
            need_restart = True
        elif backend == "ts3" and getattr(self.voice_thread, 'api_key', None) != self.cfg.get("api_key", ""):
            need_restart = True
        elif backend == "mumble" and getattr(self.voice_thread, 'port', None) != self.cfg.get("mumble_port", 25640):
            need_restart = True
        elif backend == "discord" and getattr(self.voice_thread, 'access_token', None) != self.cfg.get("discord_access_token", ""):
            need_restart = True

        if need_restart:
            self.start_voice_backend()

        # Force visibility sync for newly added overlays
        if hasattr(self, 'tracker') and hasattr(self.tracker, 'last_state'):
            self.on_active_window_changed(self.tracker.last_state)

    def _on_discord_token_saved(self, token):
        self.cfg["discord_access_token"] = token
        self.save_config()

    def start_voice_backend(self):
        if hasattr(self, 'voice_thread') and self.voice_thread is not None:
            try:
                self.voice_thread.stop()
            except Exception:
                pass
            self.voice_thread = None

        # Clear overlay users when switching voice backend
        self.on_clients_updated([], None)

        backend = self.cfg.get("voice_backend", "ts3")
        self.voice_backend = backend

        if backend == "discord":
            from discord_client import DiscordClientThread
            self.voice_thread = DiscordClientThread(
                client_id=self.cfg.get("discord_client_id", "207646673902501888"),
                access_token=self.cfg.get("discord_access_token", ""),
                token_save_callback=self._on_discord_token_saved
            )
        elif backend == "mumble":
            from mumble_client import MumbleClientThread
            self.voice_thread = MumbleClientThread(port=self.cfg.get("mumble_port", 25640))
        else:
            from ts3_client import TS3ClientThread
            self.voice_thread = TS3ClientThread(self.cfg.get("api_key", ""))

        self.ts3_thread = self.voice_thread  # Backwards compatibility
        self.voice_thread.clients_updated.connect(self.on_clients_updated)
        self.voice_thread.error_occurred.connect(self.on_voice_error)
        self.voice_thread.start()
        
    def on_settings_closed(self):
        self.settings_dialog = None
        for overlay in self.overlays.values():
            overlay.set_move_mode(False)
            
        # Force visibility sync after settings close
        if hasattr(self, 'tracker') and hasattr(self.tracker, 'last_state'):
            self.on_active_window_changed(self.tracker.last_state)

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
            
    def on_voice_error(self, err_msg):
        # Just print for now, maybe add tray notification later
        print(err_msg)

    def on_ts3_error(self, err_msg):
        self.on_voice_error(err_msg)

    def quit(self):
        from tts_manager import get_tts_manager
        get_tts_manager().stop()
        if hasattr(self, 'voice_thread') and self.voice_thread:
            self.voice_thread.stop()
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
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        handle_exception(exc_type, exc_value, exc_tb)
        sys.exit(1)
