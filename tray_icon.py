from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import pyqtSignal

class TrayIcon(QSystemTrayIcon):
    move_toggled = pyqtSignal(bool)
    mute_toggled = pyqtSignal(bool)
    overlay_toggled = pyqtSignal(str, bool)
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None, initial_mute=False, overlays_config=None):
        super().__init__(parent)
        
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.setIcon(QIcon(icon_path))
        self.setToolTip("KOverlay v0.1.10")
        
        # Create menu
        self.menu = QMenu()
        
        self.move_action = self.menu.addAction("Move Overlays")
        self.move_action.setCheckable(True)
        self.move_action.toggled.connect(self.move_toggled.emit)
        
        self.mute_action = self.menu.addAction("Mute TTS Voice")
        self.mute_action.setCheckable(True)
        self.mute_action.setChecked(initial_mute)
        self.mute_action.toggled.connect(self.mute_toggled.emit)
        
        self.menu.addSeparator()
        
        self.overlay_actions = {}
        if overlays_config is None:
            overlays_config = {}
            
        for o_id in ["1", "2", "3", "4"]:
            cfg = overlays_config.get(o_id, {})
            action = self.menu.addAction(f"Show Overlay {o_id}")
            action.setCheckable(True)
            action.setChecked(cfg.get("enabled", False))
            action.toggled.connect(lambda checked, oid=o_id: self.overlay_toggled.emit(oid, checked))
            self.overlay_actions[o_id] = action

        self.menu.addSeparator()
        
        self.settings_action = self.menu.addAction("Settings")
        self.settings_action.triggered.connect(self.settings_requested.emit)
        
        self.menu.addSeparator()
        
        self.quit_action = self.menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_requested.emit)
        
        self.setContextMenu(self.menu)

    def update_overlay_state(self, overlay_id, is_enabled):
        if overlay_id in self.overlay_actions:
            self.overlay_actions[overlay_id].blockSignals(True)
            self.overlay_actions[overlay_id].setChecked(is_enabled)
            self.overlay_actions[overlay_id].blockSignals(False)
