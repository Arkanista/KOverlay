from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import pyqtSignal

class TrayIcon(QSystemTrayIcon):
    move_toggled = pyqtSignal(bool)
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setIcon(QIcon("icon.svg"))
        self.setToolTip("TS3 Overlay")
        
        # Create menu
        self.menu = QMenu()
        
        self.move_action = self.menu.addAction("Move")
        self.move_action.setCheckable(True)
        self.move_action.toggled.connect(self.move_toggled.emit)
        
        self.settings_action = self.menu.addAction("Settings")
        self.settings_action.triggered.connect(self.settings_requested.emit)
        
        self.menu.addSeparator()
        
        self.quit_action = self.menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_requested.emit)
        
        self.setContextMenu(self.menu)
