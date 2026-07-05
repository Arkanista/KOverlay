import sys, os
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
tray = QSystemTrayIcon(QIcon("icon.svg"))
menu = QMenu()
a1 = menu.addAction("Checkable 1")
a1.setCheckable(True)
def reopen():
    menu.popup(QCursor.pos())
a1.triggered.connect(reopen)
menu.addAction("Quit").triggered.connect(app.quit)
tray.setContextMenu(menu)
tray.show()
