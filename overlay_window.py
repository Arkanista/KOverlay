from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen

class OverlayWindow(QWidget):
    blink_finished = pyqtSignal()

    def __init__(self, config, overlay_id, numeric_id, parent=None):
        super().__init__(parent)
        self.config = config
        self.overlay_id = str(overlay_id)
        self.numeric_id = numeric_id
        self.move_mode = False
        self.is_blinking = False
        self.blink_count = 0
        self.blink_state = False
        
        # Give this widget an object name to apply styles exclusively
        self.setObjectName("OverlayWindowMain")
        
        # Setup window properties
        # With X11 bypass, ToolTip correctly prevents taskbar entry and maps perfectly
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.BypassWindowManagerHint |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(2)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.layout)
        
        # Build Header Widget
        self.header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        self.icon_label = QLabel("•••")
        self.icon_label.setStyleSheet("color: rgba(255, 255, 255, 180); font-weight: bold; font-size: 14px;")
        self.icon_label.setVisible(self.config.get("show_three_dots", False))
        
        self.logo_label = QLabel()
        from PyQt6.QtGui import QPixmap
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icon.svg")
        pixmap = QPixmap(icon_path).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.logo_label.setPixmap(pixmap)
        
        self.title_label = QLabel(f"TS3 Overlay - ID {self.numeric_id}")
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: white;")
        
        header_layout.addWidget(self.icon_label)
        header_layout.addWidget(self.logo_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        self.header_widget.setLayout(header_layout)
        
        self.layout.addWidget(self.header_widget)
        
        # Container for users to separate them from the header
        self.users_container = QVBoxLayout()
        self.users_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(self.users_container)
        
        self.labels = {}
        
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._on_blink_tick)
        
        self.setMinimumSize(50, 20)
        self.resize(200, 300)
        
        mon_cfg = self.config.get("overlay_ids", {}).get(self.overlay_id, {})
        if "pos_x" in mon_cfg and "pos_y" in mon_cfg:
            self.move(mon_cfg["pos_x"], mon_cfg["pos_y"])
        else:
            offset = 50 * self.numeric_id
            self.move(offset, offset)
            
        self.update_style()
        
    def showEvent(self, event):
        super().showEvent(event)
        mon_cfg = self.config.get("overlay_ids", {}).get(self.overlay_id, {})
        if "pos_x" in mon_cfg and "pos_y" in mon_cfg:
            self.move(mon_cfg["pos_x"], mon_cfg["pos_y"])
        else:
            offset = 50 * self.numeric_id
            self.move(offset, offset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        opacity_normal = self.config.get("opacity_normal", 0.0)
        opacity_move = self.config.get("opacity_move", self.config.get("opacity", 0.8))
        hex_color = self.config.get("bg_color", "#000000")
        
        c = QColor(hex_color)
        
        if self.move_mode:
            c.setAlphaF(opacity_move)
            painter.setPen(QPen(QColor("#666666"), 2, Qt.PenStyle.DashLine))
        else:
            if getattr(self, 'is_blinking', False) and getattr(self, 'blink_state', False):
                c.setAlphaF(max(opacity_normal, 0.4))
                painter.setPen(QPen(QColor("red"), 3, Qt.PenStyle.SolidLine))
            else:
                c.setAlphaF(opacity_normal)
                painter.setPen(Qt.PenStyle.NoPen)
                
        painter.setBrush(c)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 5, 5)
        
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
        
        flags = Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.BypassWindowManagerHint
        if not self.move_mode:
            flags |= Qt.WindowType.WindowTransparentForInput
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            
            # Save position when exiting move mode (backup)
            if "overlay_ids" not in self.config:
                self.config["overlay_ids"] = {}
            if self.overlay_id not in self.config["overlay_ids"]:
                self.config["overlay_ids"][self.overlay_id] = {}
                
            self.config["overlay_ids"][self.overlay_id]["pos_x"] = self.pos().x()
            self.config["overlay_ids"][self.overlay_id]["pos_y"] = self.pos().y()
            if hasattr(self, 'save_callback'):
                self.save_callback()
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            
        self.setWindowFlags(flags)
        self.update_style()
        self.show()
        
    def update_style(self):
        show_header = self.config.get("show_header", True)
        show_three_dots = self.config.get("show_three_dots", False)
        
        dots_str = "•" * self.numeric_id
        self.icon_label.setText(dots_str)
        
        if show_header or show_three_dots:
            self.header_widget.setVisible(True)
            if not show_header and show_three_dots:
                self.icon_label.setVisible(True)
                self.logo_label.setVisible(False)
                self.title_label.setVisible(False)
            elif show_header and not show_three_dots:
                self.icon_label.setVisible(False)
                self.logo_label.setVisible(True)
                self.title_label.setVisible(True)
            else:
                self.icon_label.setVisible(True)
                self.logo_label.setVisible(True)
                self.title_label.setVisible(True)
        else:
            self.header_widget.setVisible(False)
        
        # Trigger a repaint
        self.update()
        
        # Update fonts on style change
        font_family = self.config.get("font_family", "Sans Serif")
        font_size = self.config.get("font_size", 11)
        for lbl in self.labels.values():
            font = lbl.font()
            font.setFamily(font_family)
            font.setPointSize(font_size)
            lbl.setFont(font)
            
        # Update width settings
        dynamic_width = self.config.get("dynamic_width", True)
        fixed_width = self.config.get("fixed_width", 200)
        
        if dynamic_width:
            self.setMinimumWidth(50)
            self.setMaximumWidth(16777215)
            self.adjustSize()
        else:
            self.setFixedWidth(fixed_width)
            self.adjustSize()
        
    def update_clients(self, clients):
        # Update existing or add new
        current_names = set()
        
        font_family = self.config.get("font_family", "Sans Serif")
        font_size = self.config.get("font_size", 11)
        
        for client in clients:
            name = client["name"]
            talking = client["talking"]
            current_names.add(name)
            
            if name not in self.labels:
                lbl = QLabel(name)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                font = lbl.font()
                font.setFamily(font_family)
                font.setPointSize(font_size)
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
        
        self.adjustSize()

    # Mouse events for dragging when in move mode
    def mousePressEvent(self, event):
        if self.move_mode and event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.window_start_pos = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.move_mode and event.buttons() == Qt.MouseButton.LeftButton:
            if hasattr(self, 'drag_start_pos') and hasattr(self, 'window_start_pos'):
                delta = event.globalPosition().toPoint() - self.drag_start_pos
                self.move(self.window_start_pos + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.move_mode and event.button() == Qt.MouseButton.LeftButton:
            if "overlay_ids" not in self.config:
                self.config["overlay_ids"] = {}
            if self.overlay_id not in self.config["overlay_ids"]:
                self.config["overlay_ids"][self.overlay_id] = {}
                
            self.config["overlay_ids"][self.overlay_id]["pos_x"] = self.pos().x()
            self.config["overlay_ids"][self.overlay_id]["pos_y"] = self.pos().y()
            if hasattr(self, 'save_callback'):
                self.save_callback()
            event.accept()
