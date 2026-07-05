import sys, os
os.environ["QT_QPA_PLATFORM"] = "xcb"
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QCursor

class KeepOpenMenu(QMenu):
    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action and action.isCheckable():
            action.trigger()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
tray = QSystemTrayIcon(QIcon("icon.svg"))
menu = KeepOpenMenu()
a1 = menu.addAction("Checkable 1")
a1.setCheckable(True)
menu.addAction("Quit").triggered.connect(app.quit)

def on_activated(reason):
    if reason == QSystemTrayIcon.ActivationReason.Context:
        menu.popup(QCursor.pos())

tray.activated.connect(on_activated)
tray.show()
