import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QLineEdit, QGroupBox
)
from PyQt6.QtCore import Qt, QEventLoop
from PyQt6.QtGui import QIcon

DEFAULT_DIGIT_REPLACEMENTS = {
    "0": "o",
    "1": "i",
    "2": "z",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "b",
    "7": "t",
    "8": "b",
    "9": "g"
}

DIGIT_NOTES = {
    "0": "0 ➔ o (letter O)",
    "1": "1 ➔ i (letter I)",
    "2": "2 ➔ z (letter Z)",
    "3": "3 ➔ e (letter E)",
    "4": "4 ➔ a (letter A)",
    "5": "5 ➔ s (letter S)",
    "6": "6 ➔ b (letter B)",
    "7": "7 ➔ t (letter T)",
    "8": "8 ➔ b (letter B)",
    "9": "9 ➔ g (letter G)"
}

class DigitsWindow(QWidget):
    Accepted = 1
    Rejected = 0

    def __init__(self, current_replacements=None, parent=None):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("TTS Digit Substitutions")
        self.resize(480, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.parent_window = parent
        if parent:
            geo = parent.geometry()
            self.move(
                geo.x() + (geo.width() - 480) // 2,
                geo.y() + (geo.height() - 520) // 2
            )

        self._loop = None
        self._result = self.Rejected
        
        # Merge given replacements with defaults
        self.replacements = DEFAULT_DIGIT_REPLACEMENTS.copy()
        if current_replacements and isinstance(current_replacements, dict):
            for d in map(str, range(10)):
                if d in current_replacements:
                    self.replacements[d] = current_replacements[d]
        self.replacements_result = self.replacements.copy()

        layout = QVBoxLayout(self)

        info_lbl = QLabel(
            "Substitute numbers with letters to make gamer tags pronounceable by TTS.<br>"
            "<i>(Leave replacement blank to keep the number unchanged).</i>"
        )
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Digit", "Replacement", "Preset / Suggestion"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 60)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 170)
        layout.addWidget(self.table)

        # Quick preset buttons
        presets_layout = QHBoxLayout()
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_all)
        presets_layout.addWidget(self.reset_btn)
        presets_layout.addWidget(self.clear_btn)
        presets_layout.addStretch()
        layout.addLayout(presets_layout)

        # Live preview group
        preview_group = QGroupBox("Live Pronunciation Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Sample:"))
        self.preview_input = QLineEdit("M4R10_77 (2ebra, 8oss, 9amer)")
        self.preview_input.textChanged.connect(self._update_preview)
        in_row.addWidget(self.preview_input)
        preview_layout.addLayout(in_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Spoken:"))
        self.preview_output = QLineEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setStyleSheet("font-weight: bold; color: #4caf50;")
        out_row.addWidget(self.preview_output)
        preview_layout.addLayout(out_row)

        layout.addWidget(preview_group)

        # Bottom buttons: Cancel and Save
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        self._populate_table()
        self.table.itemChanged.connect(self._on_table_item_changed)
        self._update_preview()

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
        self.replacements_result = self._extract_replacements_from_table()
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
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i in range(10):
            d_str = str(i)
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Digit cell (read only, centered)
            digit_item = QTableWidgetItem(d_str)
            digit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            digit_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, digit_item)

            # Replacement cell (editable)
            rep_val = self.replacements.get(d_str, "")
            rep_item = QTableWidgetItem(rep_val)
            rep_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, rep_item)

            # Note cell (read-only)
            note_val = DIGIT_NOTES.get(d_str, "")
            note_item = QTableWidgetItem(note_val)
            note_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            note_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, note_item)
        self.table.blockSignals(False)

    def _reset_to_defaults(self):
        self.replacements = DEFAULT_DIGIT_REPLACEMENTS.copy()
        self._populate_table()
        self._update_preview()

    def _clear_all(self):
        self.replacements = {str(i): "" for i in range(10)}
        self._populate_table()
        self._update_preview()

    def _on_table_item_changed(self, item):
        self._update_preview()

    def _extract_replacements_from_table(self):
        reps = {}
        for row in range(self.table.rowCount()):
            d_item = self.table.item(row, 0)
            r_item = self.table.item(row, 1)
            if d_item:
                d = d_item.text().strip()
                r = r_item.text().strip() if r_item else ""
                reps[d] = r
        return reps

    def _update_preview(self):
        reps = self._extract_replacements_from_table()
        sample = self.preview_input.text()
        if not sample:
            self.preview_output.setText("")
            return

        from tts_manager import apply_digit_replacements
        res = apply_digit_replacements(sample, reps)
        lowercase = True
        if hasattr(self, 'parent_window') and self.parent_window:
            cb = getattr(self.parent_window, 'tts_lowercase_checkbox', None)
            if cb is not None:
                lowercase = cb.isChecked()
        if lowercase:
            res = res.lower()
        self.preview_output.setText(res)

    def get_replacements(self):
        if hasattr(self, 'replacements_result'):
            return self.replacements_result
        return self._extract_replacements_from_table()
