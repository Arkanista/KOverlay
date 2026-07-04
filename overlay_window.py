from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class OverlayWindow(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.move_mode = False
        
        # Setup window properties
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)
        
        self.labels = {}
        
        self.resize(200, 300)
        self.update_style()
        
    def set_move_mode(self, enabled):
        self.move_mode = enabled
        
        # Toggle clickthrough
        # On some platforms, toggling flags requires hide/show to apply
        self.hide()
        if self.move_mode:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            
        self.update_style()
        self.show()
        
    def update_style(self):
        opacity = self.config.get("opacity", 0.8)
        # Background when moving
        if self.move_mode:
            bg_color = f"rgba(20, 20, 20, {opacity})"
            border = "border: 2px dashed #666;"
        else:
            bg_color = "rgba(0, 0, 0, 0)" # Fully transparent background when not moving
            border = "border: none;"
            
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                {border}
                border-radius: 5px;
            }}
        """)
        
    def update_clients(self, clients):
        # Update existing or add new
        current_names = set()
        
        for client in clients:
            name = client["name"]
            talking = client["talking"]
            current_names.add(name)
            
            if name not in self.labels:
                lbl = QLabel(name)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                font = lbl.font()
                font.setPointSize(11)
                font.setBold(True)
                lbl.setFont(font)
                self.layout.addWidget(lbl)
                self.labels[name] = lbl
                
            # Style based on talking status
            # Bright cyan/green for talking, dimmed white for not
            lbl = self.labels[name]
            if talking:
                lbl.setStyleSheet("color: #00FFCC; background-color: transparent; border: none; text-shadow: 1px 1px 2px #000;")
            else:
                lbl.setStyleSheet("color: rgba(255, 255, 255, 150); background-color: transparent; border: none; text-shadow: 1px 1px 2px #000;")
                
        # Remove old clients
        to_remove = []
        for name, lbl in self.labels.items():
            if name not in current_names:
                self.layout.removeWidget(lbl)
                lbl.deleteLater()
                to_remove.append(name)
                
        for name in to_remove:
            del self.labels[name]

    # Mouse events for dragging when in move mode
    def mousePressEvent(self, event):
        if self.move_mode and event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.move_mode and event.buttons() == Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + diff)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()
