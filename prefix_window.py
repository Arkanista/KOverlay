import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt, QEventLoop

class PrefixWindow(QWidget):
    Accepted = 1
    Rejected = 0

    def __init__(self, current_prefixes, parent=None):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Nickname Prefixes & Tags")
        self.resize(380, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        self.parent_window = parent
        if parent:
            geo = parent.geometry()
            self.move(
                geo.x() + (geo.width() - 380) // 2,
                geo.y() + (geo.height() - 320) // 2
            )

        self._loop = None
        self._result = self.Rejected
        self.prefixes = list(current_prefixes) if current_prefixes else []
        self.prefixes_result = list(self.prefixes)

        layout = QVBoxLayout(self)

        info_lbl = QLabel(
            "Enter prefixes to strip from nicknames (e.g. <b>[VIP]</b>, <b>CLAN |</b>).<br>"
            "Enter <b>[]</b>, <b>()</b>, or <b>{}</b> to strip any tag in brackets."
        )
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Prefix to Remove"])
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
        self.prefixes_result = self._extract_prefixes_from_table()
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
        for p in self.prefixes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(p)))

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem("")
        self.table.setItem(row, 0, item)
        self.table.editItem(item)

    def _del_row(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            self.table.removeRow(curr_row)

    def _extract_prefixes_from_table(self):
        result = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.text().strip():
                result.append(item.text().strip())
        return result

    def get_prefixes(self):
        if hasattr(self, 'prefixes_result'):
            return self.prefixes_result
        return self._extract_prefixes_from_table()
