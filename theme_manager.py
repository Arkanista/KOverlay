"""
theme_manager.py - System Dark/Light Mode synchronization for KOverlay.

On Linux:
  Keeps the native desktop environment theme (KDE Breeze, GNOME, etc.) untouched.

On Windows:
  Detects Windows 10/11 Dark/Light mode from the Windows Registry (AppsUseLightTheme),
  sets Qt Fusion style with a tailored dark or light palette, enables native immersive
  dark titlebars via DWM API, and monitors for live system theme changes.
"""

import sys
import ctypes
from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

_last_windows_dark_state = None

def is_windows_dark_mode() -> bool:
    """Check if Windows 10/11 app theme is set to Dark Mode."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        return False

def get_dark_palette() -> QPalette:
    """Generate a clean, high-contrast modern dark palette for Qt Fusion."""
    palette = QPalette()
    dark_bg = QColor(32, 32, 32)
    input_bg = QColor(24, 24, 24)
    button_bg = QColor(48, 48, 48)
    text_color = QColor(240, 240, 240)
    accent_blue = QColor(0, 120, 212)
    accent_link = QColor(59, 130, 246)
    disabled_text = QColor(130, 130, 130)

    # Active / Inactive states
    palette.setColor(QPalette.ColorRole.Window, dark_bg)
    palette.setColor(QPalette.ColorRole.WindowText, text_color)
    palette.setColor(QPalette.ColorRole.Base, input_bg)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.ToolTipBase, dark_bg)
    palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    palette.setColor(QPalette.ColorRole.Text, text_color)
    palette.setColor(QPalette.ColorRole.Button, button_bg)
    palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, accent_link)
    palette.setColor(QPalette.ColorRole.Highlight, accent_blue)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    # Disabled state
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_text)

    return palette

def set_windows_dark_titlebar(window, is_dark: bool):
    """Enable or disable native immersive dark titlebar on Windows 10/11."""
    if sys.platform != "win32" or window is None:
        return
    try:
        hwnd = int(window.winId())
        val = ctypes.c_int(1 if is_dark else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 on Win11 & Win10 20H1+, 19 on older Win10
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
        )
        if res != 0:
            DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, ctypes.byref(val), ctypes.sizeof(val)
            )
    except Exception:
        pass

def apply_app_theme(app: QApplication, windows=None):
    """
    Applies appropriate theme to the application.
    Does nothing on Linux (preserves native desktop theme).
    On Windows, applies Dark or Light mode according to Windows personalization settings.
    """
    global _last_windows_dark_state
    if sys.platform != "win32":
        return

    is_dark = is_windows_dark_mode()
    _last_windows_dark_state = is_dark

    if is_dark:
        app.setStyle("Fusion")
        app.setPalette(get_dark_palette())
        app.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #f0f0f0;
                border: 1px solid #3f3f46;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 26px 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #71717a;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3f3f46;
                margin: 4px 8px;
            }
        """)
    else:
        # Restore standard Windows style and light palette
        styles = QStyleFactory.keys()
        if "windowsvista" in styles:
            app.setStyle("windowsvista")
        elif "Windows" in styles:
            app.setStyle("Windows")
        else:
            app.setStyle("Fusion")
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("")

    if windows:
        for w in windows:
            if w is not None:
                apply_window_theme(w)

def apply_window_theme(window):
    """Apply titlebar and banner styling to an active window on Windows."""
    if sys.platform != "win32" or window is None:
        return
    is_dark = is_windows_dark_mode()
    set_windows_dark_titlebar(window, is_dark)
    if hasattr(window, "_update_banner_style"):
        window._update_banner_style()

def check_and_update_theme(app: QApplication, windows=None) -> bool:
    """
    Periodic check for Windows theme change.
    Returns True if theme changed and was reapplied.
    """
    global _last_windows_dark_state
    if sys.platform != "win32":
        return False

    current_state = is_windows_dark_mode()
    if _last_windows_dark_state is None or current_state != _last_windows_dark_state:
        apply_app_theme(app, windows)
        return True
    return False
