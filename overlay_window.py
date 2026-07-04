from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen
import time

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
        self.user_history = {}
        
        # Give this widget an object name to apply styles exclusively
        self.setObjectName("OverlayWindowMain")
        
        # Setup window properties
        # With X11 bypass, ToolTip correctly prevents taskbar entry and maps perfectly
        self.setWindowFlags(
            Qt.WindowType.SplashScreen |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.BypassWindowManagerHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.NoDropShadowWindowHint
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
        
        self.title_label = QLabel(f"KOverlay - ID {self.numeric_id}")
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
                self.header_widget.layout().setContentsMargins(0, 0, 0, 0)
                self.icon_label.setStyleSheet("color: rgba(255, 255, 255, 180); font-weight: bold; font-size: 16px; padding: 0px; margin: 0px;")
                self.icon_label.setFixedHeight(12)
                self.layout.setContentsMargins(10, 2, 10, 10)
            elif show_header and not show_three_dots:
                self.icon_label.setVisible(False)
                self.logo_label.setVisible(True)
                self.title_label.setVisible(True)
                self.icon_label.setMinimumHeight(0)
                self.icon_label.setMaximumHeight(16777215)
                self.header_widget.layout().setContentsMargins(0, 0, 0, 10)
                self.layout.setContentsMargins(10, 10, 10, 10)
            else:
                self.icon_label.setVisible(True)
                self.logo_label.setVisible(True)
                self.title_label.setVisible(True)
                self.icon_label.setMinimumHeight(0)
                self.icon_label.setMaximumHeight(16777215)
                self.header_widget.layout().setContentsMargins(0, 0, 0, 10)
                self.layout.setContentsMargins(10, 10, 10, 10)
        else:
            self.header_widget.setVisible(False)
            self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Trigger a repaint
        self.update()
        
        # Update fonts and colors on style change
        font_family = self.config.get("font_family", "Sans Serif")
        font_size = self.config.get("font_size", 11)
        col_normal = self.config.get('text_color_normal', '#96ffffff')
        if col_normal.startswith('rgba'): col_normal = '#96ffffff'
        
        for lbl in self.labels.values():
            font = lbl.font()
            font.setFamily(font_family)
            font.setPointSize(font_size)
            lbl.setFont(font)
            
            # If we don't know talking state here, we just apply normal color or preserve talking color
            # Actually, we can check its current color, but it's better to just wait for next tick or apply normal
            # For immediate feedback on normal color:
            if "#00FFCC" not in lbl.styleSheet() and col_normal not in lbl.styleSheet():
                # We can't perfectly know talking state without clients list, but we can guess based on current stylesheet
                # If it currently has the old talking color or new talking color:
                if "transparent" in lbl.styleSheet():
                    pass # We will let update_clients handle the color toggle

            
        # Update width settings
        dynamic_width = self.config.get("dynamic_width", True)
        fixed_width = self.config.get("fixed_width", 200)
        
        if dynamic_width:
            self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
            self.setMinimumWidth(50)
            self.setMaximumWidth(16777215)
        else:
            self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)
            self.setMinimumWidth(50)
            self.setMaximumWidth(16777215)
            self.setFixedWidth(fixed_width)
        
    def update_clients(self, clients, my_cid=None):
        import time
        current_time = time.time()
        
        history_enabled = self.config.get("history_enabled", False)
        history_duration = self.config.get("history_duration", 60)
        
        # Determine who is active right now
        active_names = {c["name"] for c in clients}
        
        changed_channel = False
        if hasattr(self, 'current_cid') and self.current_cid != my_cid:
            self.user_history.clear()
            changed_channel = True
        self.current_cid = my_cid
        
        was_empty = len(self.user_history) == 0
        
        # Update user history
        if history_enabled:
            # Mark new users
            for c in clients:
                name = c["name"]
                if name not in self.user_history:
                    # User wasn't seen before, they joined now
                    join_time = 0 if (was_empty or changed_channel) else current_time
                    self.user_history[name] = {"join_time": join_time, "leave_time": None}
                    
                    if not (was_empty or changed_channel) and self.config.get("tts_enabled", False) and not self.config.get("tts_muted", False) and getattr(self, "is_primary", False):
                        delay = self.config.get("tts_delay_ms", 0)
                        if delay == 0:
                            self._play_tts(name)
                        else:
                            QTimer.singleShot(delay, lambda n=name: self._play_tts(n))
                else:
                    # User is known, if they previously left, they are back
                    if self.user_history[name]["leave_time"] is not None:
                        # Re-joined! We update join_time and clear leave_time
                        self.user_history[name] = {"join_time": current_time, "leave_time": None}
                        
                        if self.config.get("tts_enabled", False) and not self.config.get("tts_muted", False) and getattr(self, "is_primary", False):
                            delay = self.config.get("tts_delay_ms", 0)
                            if delay == 0:
                                self._play_tts(name)
                            else:
                                QTimer.singleShot(delay, lambda n=name: self._play_tts(n))
            
            # Mark users who left
            for name, data in list(self.user_history.items()):
                if name not in active_names:
                    if data["leave_time"] is None:
                        # User just left
                        data["leave_time"] = current_time
                    elif current_time - data["leave_time"] > history_duration:
                        # User left longer than history_duration, remove from history
                        del self.user_history[name]
        else:
            # History disabled, just match active clients directly
            self.user_history = {}
            for c in clients:
                self.user_history[c["name"]] = {"join_time": 0, "leave_time": None}

        font_family = self.config.get("font_family", "Sans Serif")
        font_size = self.config.get("font_size", 11)
        
        col_normal = self.config.get('text_color_normal', '#96ffffff')
        if col_normal.startswith('rgba'): col_normal = '#96ffffff'
        col_talking = self.config.get('text_color_talking', '#00FFCC')
        if col_talking.startswith('rgba'): col_talking = '#00FFCC'
        col_left = self.config.get('text_color_left', '#808080')
        if col_left.startswith('rgba'): col_left = '#808080'

        # Build ordered list of names to display
        display_names = list(self.user_history.keys())
            
        # We need to sort: active first, then left users
        def sort_key(name):
            data = self.user_history[name]
            is_left = data["leave_time"] is not None
            return (1 if is_left else 0, name.lower())
            
        display_names.sort(key=sort_key)
        
        # Remove old labels not in display_names
        to_remove = []
        for name, lbl in self.labels.items():
            if name not in display_names:
                self.users_container.removeWidget(lbl)
                lbl.deleteLater()
                to_remove.append(name)
                
        for name in to_remove:
            del self.labels[name]
            
        # Rebuild/update labels
        for name in display_names:
            data = self.user_history[name]
            is_left = data["leave_time"] is not None
            is_new = history_enabled and not is_left and (current_time - data["join_time"] < history_duration)
            
            # Format text
            display_text = name
            if is_left:
                display_text = "✝ " + name
            elif is_new:
                display_text = "+ " + name
                
            # Get talking state
            talking = next((c["talking"] for c in clients if c["name"] == name), False)
            
            # Create or update label
            if name not in self.labels:
                lbl = QLabel(display_text)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                font = lbl.font()
                font.setFamily(font_family)
                font.setPointSize(font_size)
                font.setBold(True)
                lbl.setFont(font)
                self.labels[name] = lbl
            else:
                lbl = self.labels[name]
                lbl.setText(display_text)
                
            # Remove from layout and re-add to enforce order
            self.users_container.removeWidget(lbl)
            self.users_container.addWidget(lbl)
            
            # Apply style
            if is_left:
                lbl.setStyleSheet(f"color: {col_left}; background-color: transparent; border: none;")
            elif talking:
                lbl.setStyleSheet(f"color: {col_talking}; background-color: transparent; border: none;")
            else:
                lbl.setStyleSheet(f"color: {col_normal}; background-color: transparent; border: none;")
                
        if self.config.get("dynamic_width", True):
            # Layout constraint will automatically resize the window
            pass
        else:
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

    def _play_tts(self, name):
        import subprocess
        import shutil
        import tempfile
        import os
        import threading
        import hashlib
        
        if self.config.get("tts_enabled", False):
            # Safe filename for cache
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-")
            filename = hashlib.md5(safe_name.encode()).hexdigest() + ".mp3"
            tmp_file = os.path.join(tempfile.gettempdir(), f"koverlay_{filename}")

            import importlib.util
            import sys
            edge_tts_installed = importlib.util.find_spec("edge_tts") is not None

            if edge_tts_installed and shutil.which("mpv"):
                def run_edge_tts():
                    try:
                        # Cache the generated voice per user to save network requests & time
                        if not os.path.exists(tmp_file):
                            subprocess.run([sys.executable, "-m", "edge_tts", "--voice", "en-US-AriaNeural", "--text", f"{safe_name} joined", "--write-media", tmp_file], check=True)
                        vol = self.config.get("tts_volume", 80)
                        subprocess.Popen(["mpv", "--no-video", "--really-quiet", f"--volume={vol}", tmp_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        pass
                # Run network request in background to prevent overlay freeze
                threading.Thread(target=run_edge_tts, daemon=True).start()
                
            elif shutil.which("espeak"):
                vol = int(self.config.get("tts_volume", 80) * 2) # espeak scale is 0 to 200, default 100
                subprocess.Popen(["espeak", "-a", str(vol), "-v", "en", f"{name} joined"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("spd-say"):
                vol = int((self.config.get("tts_volume", 80) - 50) * 2) # spd-say is -100 to +100
                subprocess.Popen(["spd-say", "-y", str(vol), "-l", "en", f"{name} joined"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
