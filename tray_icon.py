from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import pyqtSignal

class TrayIcon(QSystemTrayIcon):
    move_toggled = pyqtSignal(bool)
    mute_toggled = pyqtSignal(bool)
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None, initial_mute=False):
        super().__init__(parent)
        
        self.setIcon(QIcon("icon.svg"))
        self.setToolTip("KOverlay v0.1.7")
        
        # Create menu
        self.menu = QMenu()
        
        self.move_action = self.menu.addAction("Move Overlays")
        self.move_action.setCheckable(True)
        self.move_action.toggled.connect(self.move_toggled.emit)
        
        self.mute_action = self.menu.addAction("Mute TTS Voice")
        self.mute_action.setCheckable(True)
        self.mute_action.setChecked(initial_mute)
        self.mute_action.toggled.connect(self.mute_toggled.emit)
        
        self.settings_action = self.menu.addAction("Settings")
        self.settings_action.triggered.connect(self.settings_requested.emit)
        
        self.menu.addSeparator()
        
        self.quit_action = self.menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_requested.emit)
        
        self.setContextMenu(self.menu)
