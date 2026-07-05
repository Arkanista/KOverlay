import sys
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QCheckBox, QWidgetAction
from PyQt6.QtGui import QIcon
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
tray = QSystemTrayIcon(QIcon("icon.svg"))
menu = QMenu()
cb = QCheckBox("Test Checkbox")
wa = QWidgetAction(menu)
wa.setDefaultWidget(cb)
menu.addAction(wa)
menu.addAction("Normal Action")
tray.setContextMenu(menu)
tray.show()
QTimer = app.instance().metaObject().className() # just delay
# app.exec()
