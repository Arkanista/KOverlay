import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QEventLoop

class AliasWindow(QWidget):
    Accepted = 1
    Rejected = 0

    def __init__(self, current_aliases, parent=None):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("TTS Aliases (Substitution List)")
        self.resize(400, 300)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        self.parent_window = parent
        if parent:
            geo = parent.geometry()
            self.move(
                geo.x() + (geo.width() - 400) // 2,
                geo.y() + (geo.height() - 300) // 2
            )

        self._loop = None
        self._result = self.Rejected
        self.aliases = current_aliases.copy() if current_aliases else {}
        self.aliases_result = self.aliases.copy()

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Substitute (Source)", "With (Target)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._add_row)

        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._del_row)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        layout.addLayout(btn_layout)

        save_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        save_layout.addStretch()
        save_layout.addWidget(self.cancel_btn)
        save_layout.addWidget(self.save_btn)
        layout.addLayout(save_layout)

        self._populate_table()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            import theme_manager
            theme_manager.apply_window_theme(self)
        except Exception:
            pass

    def exec(self):
        self._result = self.Rejected
        self.show()
        self.activateWindow()
        self.raise_()
        self._loop = QEventLoop()
        self._loop.exec()
        return self._result

    def accept(self):
        self._result = self.Accepted
        self.aliases_result = self._extract_aliases_from_table()
        self.close()
        if self._loop and self._loop.isRunning():
            self._loop.quit()

    def reject(self):
        self._result = self.Rejected
        self.close()
        if self._loop and self._loop.isRunning():
            self._loop.quit()

    def closeEvent(self, event):
        if self._loop and self._loop.isRunning():
            self._loop.quit()
        super().closeEvent(event)

    def _populate_table(self):
        self.table.setRowCount(0)
        for src, dst in self.aliases.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(src))
            self.table.setItem(row, 1, QTableWidgetItem(dst))

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.editItem(self.table.item(row, 0))

    def _del_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def _extract_aliases_from_table(self):
        aliases = {}
        for row in range(self.table.rowCount()):
            src_item = self.table.item(row, 0)
            dst_item = self.table.item(row, 1)

            if src_item and dst_item:
                src = src_item.text().strip()
                dst = dst_item.text()
                if src:
                    aliases[src] = dst
        return aliases

    def get_aliases(self):
        if hasattr(self, 'aliases_result'):
            return self.aliases_result
        return self._extract_aliases_from_table()
