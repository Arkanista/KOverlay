from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import pyqtSignal

class TrayIcon(QSystemTrayIcon):
    move_toggled = pyqtSignal(bool)
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create a simple icon (a blue circle for now, can be replaced with an image)
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("transparent"))
        import PyQt6.QtGui as QtGui
        from PyQt6.QtCore import Qt
        painter = QtGui.QPainter(pixmap)
        painter.setBrush(QColor("#3498db"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 64, 64)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
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
