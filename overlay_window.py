from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QPainter

class OverlayWindow(QWidget):
    blink_finished = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.move_mode = False
        self.is_blinking = False
        self.blink_count = 0
        self.blink_state = False
        
        # Give this widget an object name to apply styles exclusively
        self.setObjectName("OverlayWindowMain")
        
        # Setup window properties
        # On Wayland, Tool without parent can prevent the window from mapping
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)
        
        # Build Header Widget
        self.header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        self.icon_label = QLabel()
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("transparent"))
        painter = QPainter(pixmap)
        painter.setBrush(QColor("#3498db"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 16, 16)
        painter.end()
        self.icon_label.setPixmap(pixmap)
        
        self.title_label = QLabel("TS3 Overlay")
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: white;")
        
        header_layout.addWidget(self.icon_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        self.header_widget.setLayout(header_layout)
        
        self.layout.addWidget(self.header_widget)
        
        # Container for users to separate them from the header
        self.users_container = QVBoxLayout()
        self.layout.addLayout(self.users_container)
        
        self.labels = {}
        
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._on_blink_tick)
        
        self.resize(200, 300)
        self.update_style()
        
    def start_blink(self):
        self.is_blinking = True
        self.blink_count = 0
        self.blink_state = False
        self.show()
        self.blink_timer.start(500) # 500ms = 1Hz cycle
        self._on_blink_tick()
        
    def _on_blink_tick(self):
        self.blink_state = not self.blink_state
        self.update_style()
        self.blink_count += 1
        
        if self.blink_count >= 10: # 5 full cycles
            self.blink_timer.stop()
            self.is_blinking = False
            self.update_style()
            self.blink_finished.emit()

    def set_move_mode(self, enabled):
        self.move_mode = enabled
        
        self.hide()
        if self.move_mode:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            
        self.update_style()
        self.show()
        
    def update_style(self):
        self.header_widget.setVisible(self.config.get("show_header", True))
        
        opacity = self.config.get("opacity", 0.8)
        
        bg_color = "rgba(0, 0, 0, 0)"
        border = "border: none;"
        
        if self.move_mode:
            bg_color = f"rgba(20, 20, 20, {opacity})"
            border = "border: 2px dashed #666;"
            
        if self.is_blinking and self.blink_state:
            border = "border: 3px solid red;"
            if not self.move_mode:
                 bg_color = f"rgba(20, 20, 20, {opacity / 2.0})"
                 
        self.setStyleSheet(f"""
            QWidget#OverlayWindowMain {{
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
                self.users_container.addWidget(lbl)
                self.labels[name] = lbl
                
            # Style based on talking status
            lbl = self.labels[name]
            if talking:
                lbl.setStyleSheet("color: #00FFCC; background-color: transparent; border: none;")
            else:
                lbl.setStyleSheet("color: rgba(255, 255, 255, 150); background-color: transparent; border: none;")
                
        # Remove old clients
        to_remove = []
        for name, lbl in self.labels.items():
            if name not in current_names:
                self.users_container.removeWidget(lbl)
                lbl.deleteLater()
                to_remove.append(name)
                
        for name in to_remove:
            del self.labels[name]

    # Mouse events for dragging when in move mode
    def mousePressEvent(self, event):
        if self.move_mode and event.button() == Qt.MouseButton.LeftButton:
            window = self.windowHandle()
            if window:
                window.startSystemMove()
            event.accept()

    def mouseMoveEvent(self, event):
        # Native Wayland move handles this, so we do nothing here.
        pass
