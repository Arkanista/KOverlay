from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt

class AliasWindow(QDialog):
    def __init__(self, current_aliases, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lista Zastąpień (TTS Aliases)")
        self.resize(400, 300)
        
        self.aliases = current_aliases.copy() if current_aliases else {}
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Zastąp (Źródło)", "Na (Docelowo)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Dodaj")
        self.add_btn.clicked.connect(self._add_row)
        
        self.del_btn = QPushButton("Usuń")
        self.del_btn.clicked.connect(self._del_row)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        layout.addLayout(btn_layout)
        
        save_layout = QHBoxLayout()
        self.save_btn = QPushButton("Zapisz")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Anuluj")
        self.cancel_btn.clicked.connect(self.reject)
        
        save_layout.addStretch()
        save_layout.addWidget(self.cancel_btn)
        save_layout.addWidget(self.save_btn)
        layout.addLayout(save_layout)
        
        self._populate_table()
        
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

    def get_aliases(self):
        aliases = {}
        for row in range(self.table.rowCount()):
            src_item = self.table.item(row, 0)
            dst_item = self.table.item(row, 1)
            
            if src_item and dst_item:
                src = src_item.text().strip()
                dst = dst_item.text() # Keep spaces if they want to replace with spaces
                
                if src:  # Only add if source is not empty
                    aliases[src] = dst
        return aliases
