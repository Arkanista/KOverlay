from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen, QFont, QFontMetrics
import time
import sys
import os
import re

def interpolate_color(col_from_str, col_to_str, progress):
    progress = max(0.0, min(1.0, progress))
    c_from = QColor(col_from_str)
    c_to = QColor(col_to_str)
    if not c_from.isValid():
        c_from = QColor("#00ffcc")
    if not c_to.isValid():
        c_to = QColor("#96ffffff")
    
    r = int(c_from.red() + (c_to.red() - c_from.red()) * progress)
    g = int(c_from.green() + (c_to.green() - c_from.green()) * progress)
    b = int(c_from.blue() + (c_to.blue() - c_from.blue()) * progress)
    a = int(c_from.alpha() + (c_to.alpha() - c_from.alpha()) * progress)
    return QColor.fromRgb(r, g, b, a).name(QColor.NameFormat.HexArgb)

class UserRowWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self.row_layout = QHBoxLayout(self)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(4)
        self.row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.arrow_label = QLabel(self)
        self.arrow_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.arrow_label.setVisible(False)
        
        self.name_label = QLabel(self)
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        
        self.row_layout.addWidget(self.arrow_label)
        self.row_layout.addWidget(self.name_label)
        self.row_layout.addStretch()
        
        self._current_stylesheet = ""

    def set_content(self, clean_name: str, arrow_text: str = ""):
        self.name_label.setText(clean_name)
        if arrow_text:
            self.arrow_label.setText(arrow_text)
            self.arrow_label.setVisible(True)
        else:
            self.arrow_label.setText("")
            self.arrow_label.setVisible(False)
        self.row_layout.invalidate()
        self.updateGeometry()
            
    def setText(self, display_text: str):
        if display_text.startswith("🡅 "):
            self.set_content(display_text[2:], "🡅")
        elif display_text.startswith("🡇 "):
            self.set_content(display_text[2:], "🡇")
        else:
            self.set_content(display_text, "")

    def text(self) -> str:
        if self.arrow_label.isVisible() and self.arrow_label.text():
            return f"{self.arrow_label.text()} {self.name_label.text()}"
        return self.name_label.text()

    def setFont(self, font: QFont):
        super().setFont(font)
        self.name_label.setFont(font)
        self.arrow_label.setFont(font)
        self.row_layout.invalidate()
        self.updateGeometry()

    def font(self) -> QFont:
        return self.name_label.font()

    def setStyleSheet(self, style: str):
        self._current_stylesheet = style
        self.name_label.setStyleSheet(style)
        self.arrow_label.setStyleSheet(style)

    def styleSheet(self) -> str:
        return self._current_stylesheet

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
        self.last_talk_time = {}
        self.talking_now = {}
        self.whisper_now = {}
        self.last_talk_was_whisper = {}
        self.last_clients = []
        self.is_initial_snapshot = True
        
        # Give this widget an object name to apply styles exclusively
        self.setObjectName("OverlayWindowMain")
        
        # Setup window properties
        if sys.platform == "win32":
            # On Windows: Tool prevents taskbar entry, Frameless + WindowStaysOnTop creates transparent overlay
            flags = (
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool |
                Qt.WindowType.WindowTransparentForInput |
                Qt.WindowType.WindowDoesNotAcceptFocus |
                Qt.WindowType.NoDropShadowWindowHint
            )
        else:
            # With X11 bypass, Tool + WindowDoesNotAcceptFocus prevents taskbar entry and XWayland/KWin focus stealing
            flags = (
                Qt.WindowType.Tool |
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.BypassWindowManagerHint |
                Qt.WindowType.WindowTransparentForInput |
                Qt.WindowType.WindowDoesNotAcceptFocus |
                Qt.WindowType.NoDropShadowWindowHint
            )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(22, 22, 22, 22)
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
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
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

        self.fade_timer = QTimer(self)
        self.fade_timer.setInterval(40)
        self.fade_timer.timeout.connect(self._on_fade_tick)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self._on_refresh_tick)
        self.refresh_timer.start()
        
        self.setMinimumSize(50, 20)
        self._user_moved = False
        self._dragging = False
        self._was_right_anchored = self._is_right_anchored()
        self._last_refresh_tick_time = time.time()
        self._wake_timers = []
        
        self.update_style()
        self.apply_configured_position()

    def _is_right_anchored(self) -> bool:
        return bool(self.config.get("dynamic_width", True) and self.config.get("dynamic_width_right_anchor", False))

    def _sanitize_position(self, x, y, width=None):
        """
        Sanity check: ensures overlay (x, y) is at least partially visible on a connected monitor.
        If it is off-screen, in a multi-monitor dead zone, or on a sleeping/disconnected monitor,
        returns a temporary safe position on the primary monitor WITHOUT overwriting config.json.
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QRect
        
        app = QApplication.instance()
        screens = app.screens() if app else []
        if not screens:
            return int(x), int(y)
            
        # The top/header area of the overlay (where it can be seen and grabbed) must be on a screen.
        # Use full screen.geometry() so panel/layer-shell startup delays after sleep in KDE Plasma 6.8
        # do not invalidate valid monitor coordinates.
        check_w = max(int(width if width is not None else self.width()), 80)
        header_rect = QRect(int(x), int(y), check_w, 30)
        
        for screen in screens:
            geom = screen.geometry()
            if not geom.isValid() or geom.width() <= 0 or geom.height() <= 0:
                continue
            intersect = geom.intersected(header_rect)
            if intersect.width() >= 30 and intersect.height() >= 20:
                return int(x), int(y)  # Valid and visible
                
        # Off-screen or on a currently sleeping/disconnected monitor:
        # return temporary fallback position on primary monitor without overwriting config
        return self._get_default_position()

    def _get_configured_target_pos(self, width=None):
        """
        Returns the sanitized target (x, y) position for the overlay given its target width.
        When right-anchored dynamic width is enabled, keeps the right edge fixed at pos_right.
        """
        if width is None:
            width = max(self.width(), 50)
        width = max(int(width), 50)
        mon_cfg = self.config.get("overlay_ids", {}).get(self.overlay_id, {})
        if "pos_x" in mon_cfg and "pos_y" in mon_cfg:
            if self._is_right_anchored():
                pos_right = mon_cfg.get("pos_right")
                if pos_right is None:
                    pos_right = int(mon_cfg["pos_x"]) + width
                    mon_cfg["pos_right"] = pos_right
                raw_x = int(pos_right) - width
            else:
                raw_x = int(mon_cfg["pos_x"])
            raw_y = int(mon_cfg["pos_y"])
            return self._sanitize_position(raw_x, raw_y, width)
        return self._get_default_position()

    def apply_configured_position(self, force=False):
        """
        Moves the overlay to its saved position from config (or temporary fallback if target screen
        is currently unavailable). When force=True on Linux/XWayland, nudges the widget by 1px first
        if needed so Qt is guaranteed to emit a native ConfigureWindow to KWin.
        """
        if getattr(self, '_dragging', False):
            return
        if self.move_mode:
            mon_cfg = self.config.get("overlay_ids", {}).get(self.overlay_id, {})
            if "pos_x" not in mon_cfg or "pos_y" not in mon_cfg:
                new_x, new_y = self._get_default_position()
            else:
                new_x, new_y = self._get_configured_target_pos(self.width())
        else:
            new_x, new_y = self._get_configured_target_pos(self.width())

        new_x, new_y = int(new_x), int(new_y)
        if force and sys.platform != "win32" and self.pos().x() == new_x and self.pos().y() == new_y:
            self.move(new_x + 1, new_y)

        self.move(new_x, new_y)
        win_handle = self.windowHandle()
        if win_handle is not None:
            win_handle.setPosition(new_x, new_y)

    def _schedule_post_wake_restore(self):
        """
        Schedules multiple staggered position restorations after system sleep/resume or monitor wake
        to handle asynchronous DisplayPort/HDMI re-initialization in Plasma 6.8 and Windows.
        """
        for delay_ms in (500, 1500, 3000, 5000):
            QTimer.singleShot(delay_ms, lambda: self.apply_configured_position(force=True))

    def _get_default_position(self):
        """
        Calculates a side-by-side centered position on the primary monitor for this overlay.
        """
        from PyQt6.QtWidgets import QApplication
        
        app = QApplication.instance()
        primary = app.primaryScreen() if app else None
        if not primary and app and app.screens():
            primary = app.screens()[0]
            
        if not primary:
            offset = 50 * self.numeric_id
            return offset, offset
            
        avail = primary.availableGeometry()
        if not avail.isValid() or avail.width() <= 0 or avail.height() <= 0:
            avail = primary.geometry()
        gap = 24
        overlay_w = max(self.width(), 200)
        overlay_h = max(self.height(), 100)
        
        total_w = 4 * overlay_w + 3 * gap
        start_x = avail.x() + max(0, (avail.width() - total_w) // 2)
        center_y = avail.y() + max(0, (avail.height() - overlay_h) // 2)
        
        idx_offset = (self.numeric_id - 1) * (overlay_w + gap)
        new_x = start_x + idx_offset
        new_y = center_y
        
        new_x = min(max(new_x, avail.x()), avail.x() + max(0, avail.width() - overlay_w))
        new_y = min(max(new_y, avail.y()), avail.y() + max(0, avail.height() - overlay_h))
        return new_x, new_y
        
    def _apply_win32_click_through(self, transparent=True):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            if hwnd:
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x00080000
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_NOACTIVATE = 0x08000000
                user32 = ctypes.windll.user32
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if transparent:
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
                else:
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_LAYERED | WS_EX_NOACTIVATE) & ~WS_EX_TRANSPARENT)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_configured_position(force=False)
        self._apply_win32_click_through(not self.move_mode)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        opacity_normal = self.config.get("opacity_normal", 0.0)
        opacity_move = self.config.get("opacity_move", self.config.get("opacity", 0.8))
        hex_color = self.config.get("bg_color", "#000000")
        
        c = QColor(hex_color)
        margin = 8
        bg_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        
        if self.move_mode:
            c.setAlphaF(opacity_move)
            painter.setPen(QPen(QColor("#666666"), 2, Qt.PenStyle.DashLine))
        else:
            if getattr(self, 'is_blinking', False) and getattr(self, 'blink_state', False):
                c.setAlphaF(max(opacity_normal, 0.4))
                
                # Draw pulsating outer glow
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for i in range(1, margin + 1):
                    alpha = int(180 * (margin + 1 - i) / margin)
                    painter.setPen(QPen(QColor(255, 0, 0, alpha), 2))
                    painter.drawRoundedRect(bg_rect.adjusted(-i, -i, i, i), 6 + i/2, 6 + i/2)
                
                painter.setPen(QPen(QColor(255, 50, 50, 255), 2, Qt.PenStyle.SolidLine))
            else:
                c.setAlphaF(opacity_normal)
                painter.setPen(Qt.PenStyle.NoPen)
                
        painter.setBrush(c)
        painter.drawRoundedRect(bg_rect, 5, 5)
        
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

    def _on_fade_tick(self):
        current_time = time.time()
        fade_duration = float(self.config.get("speaker_fade_duration", 5))
        if fade_duration <= 0:
            self.fade_timer.stop()
            return

        col_normal = self.config.get('text_color_normal', '#96ffffff')
        if col_normal.startswith('rgba'): col_normal = '#96ffffff'
        col_talking = self.config.get('text_color_talking', '#00FFCC')
        if col_talking.startswith('rgba'): col_talking = '#00FFCC'
        col_whisper = self.config.get('text_color_whisper', '#ff9900')
        if col_whisper.startswith('rgba'): col_whisper = '#ff9900'

        sort_mode = self.config.get("sort_order", "alphabetical_fading_top")
        needs_resort = False

        any_fading = False
        for name, lbl in list(self.labels.items()):
            data = self.user_history.get(name, {})
            if data.get("leave_time") is not None:
                continue
            if self.talking_now.get(name, False):
                continue

            last_talk = self.last_talk_time.get(name, 0)
            elapsed = current_time - last_talk
            if last_talk > 0 and elapsed < fade_duration:
                any_fading = True
                progress = elapsed / fade_duration
                from_col = col_whisper if self.last_talk_was_whisper.get(name, False) else col_talking
                col = interpolate_color(from_col, col_normal, progress)
                lbl.setStyleSheet(f"color: {col}; background-color: transparent; border: none;")
            elif last_talk > 0 and elapsed >= fade_duration:
                if data.get("external", False):
                    needs_resort = True
                elif col_normal not in lbl.styleSheet():
                    lbl.setStyleSheet(f"color: {col_normal}; background-color: transparent; border: none;")
                    if sort_mode == "alphabetical_fading_top":
                        needs_resort = True

        if needs_resort and hasattr(self, 'last_clients') and self.last_clients is not None:
            self.update_clients(self.last_clients, getattr(self, 'current_cid', None))

        if not any_fading:
            self.fade_timer.stop()

    def _on_refresh_tick(self):
        current_time = time.time()
        last_tick = getattr(self, '_last_refresh_tick_time', current_time)
        self._last_refresh_tick_time = current_time

        # Detect system wake from suspend/sleep (1s timer jumped by > 3s)
        if current_time - last_tick > 3.0:
            self._schedule_post_wake_restore()

        if not self.move_mode and self.isVisible():
            mon_cfg = self.config.get("overlay_ids", {}).get(self.overlay_id, {})
            if "pos_x" in mon_cfg and "pos_y" in mon_cfg:
                target_x, target_y = self._get_configured_target_pos(self.width())
                if self.pos().x() != target_x or self.pos().y() != target_y:
                    self.apply_configured_position(force=True)

        if not hasattr(self, 'last_clients') or self.last_clients is None:
            return
            
        history_enabled = self.config.get("history_enabled", False)
        history_duration = float(self.config.get("history_duration", 60))

        # Only trigger an update if there is something pending expiration:
        # 1) A user who left and needs to be pruned when history_duration elapses
        # 2) A user who joined recently and still has '🡅' displayed that needs to be removed
        # 3) A user whose fade duration elapsed in alphabetical_fading_top mode
        has_pending = False
        if history_enabled:
            for data in self.user_history.values():
                if data.get("leave_time") is not None:
                    has_pending = True
                    break
                join_time = data.get("join_time", 0)
                if join_time > 0 and (current_time - join_time < history_duration + 2):
                    has_pending = True
                    break
        else:
            if any(d.get("leave_time") is not None for d in self.user_history.values()):
                has_pending = True

        if not has_pending and any(d.get("external", False) for d in self.user_history.values()):
            has_pending = True

        sort_mode = self.config.get("sort_order", "alphabetical_fading_top")
        if not has_pending and sort_mode == "alphabetical_fading_top":
            fade_duration = float(self.config.get("speaker_fade_duration", 5))
            if fade_duration > 0:
                for name, data in self.user_history.items():
                    if data.get("leave_time") is None:
                        last_talk = self.last_talk_time.get(name, 0)
                        if last_talk > 0 and (current_time - last_talk < fade_duration + 2):
                            has_pending = True
                            break

        if has_pending:
            self.update_clients(self.last_clients, getattr(self, 'current_cid', None))

    def set_move_mode(self, enabled):
        was_move_mode = getattr(self, 'move_mode', False)
        self.move_mode = enabled
        
        if sys.platform == "win32":
            flags = (
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool |
                Qt.WindowType.WindowDoesNotAcceptFocus |
                Qt.WindowType.NoDropShadowWindowHint
            )
        else:
            flags = (
                Qt.WindowType.Tool |
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.BypassWindowManagerHint |
                Qt.WindowType.WindowDoesNotAcceptFocus |
                Qt.WindowType.NoDropShadowWindowHint
            )

        if not self.move_mode:
            flags |= Qt.WindowType.WindowTransparentForInput
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            
            # Only save position when exiting move mode if the user actually dragged the window
            # or if this overlay had no saved position in config yet.
            if was_move_mode:
                self._dragging = False
                if "overlay_ids" not in self.config:
                    self.config["overlay_ids"] = {}
                if self.overlay_id not in self.config["overlay_ids"]:
                    self.config["overlay_ids"][self.overlay_id] = {}
                mon_cfg = self.config["overlay_ids"][self.overlay_id]
                if getattr(self, '_user_moved', False) or "pos_x" not in mon_cfg or "pos_y" not in mon_cfg:
                    new_x, new_y = self._sanitize_position(self.pos().x(), self.pos().y(), self.width())
                    mon_cfg["pos_x"] = new_x
                    mon_cfg["pos_y"] = new_y
                    mon_cfg["pos_right"] = new_x + self.width()
                    if hasattr(self, 'save_callback') and self.save_callback:
                        self.save_callback()
                self._user_moved = False
        else:
            self._user_moved = False
            self._dragging = False
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            
        if was_move_mode != self.move_mode:
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update_style()
        is_enabled = self.config.get("overlay_ids", {}).get(self.overlay_id, {}).get("enabled", False)
        if self.move_mode or is_enabled:
            if not self.isVisible():
                self.show()
            self.apply_configured_position(force=False)
        else:
            self.hide()
        self._apply_win32_click_through(not self.move_mode)
        
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
                self.layout.setContentsMargins(22, 10, 22, 22)
            elif show_header and not show_three_dots:
                self.icon_label.setVisible(False)
                self.logo_label.setVisible(True)
                self.title_label.setVisible(True)
                self.icon_label.setMinimumHeight(0)
                self.icon_label.setMaximumHeight(16777215)
                self.header_widget.layout().setContentsMargins(0, 0, 0, 10)
                self.layout.setContentsMargins(22, 22, 22, 22)
            else:
                self.icon_label.setVisible(True)
                self.logo_label.setVisible(True)
                self.title_label.setVisible(True)
                self.icon_label.setMinimumHeight(0)
                self.icon_label.setMaximumHeight(16777215)
                self.header_widget.layout().setContentsMargins(0, 0, 0, 10)
                self.layout.setContentsMargins(22, 22, 22, 22)
        else:
            self.header_widget.setVisible(False)
            self.layout.setContentsMargins(22, 22, 22, 22)
        
        # Trigger a repaint
        self.update()
        
        # Update fonts and colors on style change
        font_family = self.config.get("font_family", "Sans Serif")
        font_size = self.config.get("font_size", 11)
        cfg_line_height = self.config.get("line_height", 0)
        col_normal = self.config.get('text_color_normal', '#96ffffff')
        if col_normal.startswith('rgba'): col_normal = '#96ffffff'
        
        test_font = QFont(font_family, font_size, QFont.Weight.Bold)
        fm = QFontMetrics(test_font)
        row_height = cfg_line_height if (cfg_line_height and cfg_line_height > 0) else max(fm.lineSpacing(), 12)
        
        for lbl in self.labels.values():
            lbl.setFont(test_font)
            lbl.setFixedHeight(row_height)
            
            # If we don't know talking state here, we just apply normal color or preserve talking color
            # Actually, we can check its current color, but it's better to just wait for next tick or apply normal
            # For immediate feedback on normal color:
            if "#00FFCC" not in lbl.styleSheet() and col_normal not in lbl.styleSheet():
                # We can't perfectly know talking state without clients list, but we can guess based on current stylesheet
                # If it currently has the old talking color or new talking color:
                if "transparent" in lbl.styleSheet():
                    pass # We will let update_clients handle the color toggle

            
        # Update width & geometry settings
        self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)
        
        if hasattr(self, 'last_clients') and (self.last_clients or self.user_history):
            self.update_clients(self.last_clients, getattr(self, 'current_cid', None))
        else:
            self._update_overlay_geometry()

    def _update_overlay_geometry(self):
        """
        Synchronously recalculates and applies the exact width, height, and (when right-anchored)
        horizontal position of the overlay window so height always shrinks immediately when a user
        leaves and the right edge remains fixed when dynamic_width_right_anchor is enabled.
        """
        self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)
        self.setMinimumSize(50, 20)
        self.setMaximumSize(16777215, 16777215)

        for lbl in self.labels.values():
            lbl.row_layout.invalidate()
            lbl.updateGeometry()
        if self.header_widget.layout() is not None:
            self.header_widget.layout().invalidate()
        self.header_widget.updateGeometry()
        self.users_container.invalidate()
        self.layout.invalidate()
        self.layout.activate()

        hint = self.layout.totalSizeHint()
        target_h = max(20, hint.height())
        if self.config.get("dynamic_width", True):
            target_w = max(50, hint.width())
        else:
            target_w = max(50, int(self.config.get("fixed_width", 200)))

        is_right_anchored = self._is_right_anchored()
        was_right_anchored = getattr(self, "_was_right_anchored", None)
        mon_cfg = self.config.get("overlay_ids", {}).get(self.overlay_id)
        if mon_cfg is not None and "pos_x" in mon_cfg and "pos_y" in mon_cfg:
            if is_right_anchored:
                if not was_right_anchored or "pos_right" not in mon_cfg:
                    current_w = self.width() if self.width() >= 50 else target_w
                    mon_cfg["pos_right"] = int(mon_cfg["pos_x"]) + current_w
            elif was_right_anchored and "pos_right" in mon_cfg:
                current_w = self.width() if self.width() >= 50 else target_w
                mon_cfg["pos_x"] = int(mon_cfg["pos_right"]) - current_w
        self._was_right_anchored = is_right_anchored

        win_handle = self.windowHandle()
        if not getattr(self, "_dragging", False):
            if self.move_mode and (mon_cfg is None or "pos_x" not in mon_cfg or "pos_y" not in mon_cfg):
                target_x, target_y = self.pos().x(), self.pos().y()
            else:
                target_x, target_y = self._get_configured_target_pos(target_w)
            target_x, target_y = int(target_x), int(target_y)
            self.setGeometry(target_x, target_y, target_w, target_h)
            if win_handle is not None:
                win_handle.setGeometry(target_x, target_y, target_w, target_h)
        else:
            self.resize(target_w, target_h)
            if win_handle is not None:
                win_handle.resize(target_w, target_h)

        self.setFixedSize(target_w, target_h)
        self.update()

    def reset_voice_state(self):
        """Cleanly resets all user history, labels, and state without triggering leave/join events or TTS."""
        self.user_history.clear()
        self.last_talk_time.clear()
        self.talking_now.clear()
        self.whisper_now.clear()
        self.last_talk_was_whisper.clear()
        self.last_clients = []
        self.current_cid = None
        self.is_initial_snapshot = True

        for name, lbl in list(self.labels.items()):
            self.users_container.removeWidget(lbl)
            lbl.hide()
            lbl.setParent(None)
            lbl.deleteLater()
        self.labels.clear()

        if hasattr(self, 'fade_timer') and self.fade_timer.isActive():
            self.fade_timer.stop()

        self._update_overlay_geometry()

    def update_clients(self, clients=None, my_cid=None):
        if clients is None:
            clients = getattr(self, 'last_clients', [])
        if my_cid is None:
            my_cid = getattr(self, 'current_cid', None)

        # Filter out unknown/placeholder/User_XX names so they are never displayed or announced
        clean_clients = []
        for c in clients:
            name = (c.get("name") or "").strip()
            if not name or re.match(r"^[Uu]ser_\d+$", name) or name.lower() == "unknown":
                continue
            clean_clients.append(c)
        clients = clean_clients

        # If disconnected from voice / not in any channel
        if not clients and my_cid is None:
            self.reset_voice_state()
            return

        self.last_clients = clients
        import time
        current_time = time.time()

        # Purge any previously stored invalid placeholder users from history
        for k in list(self.user_history.keys()):
            if not k or re.match(r"^[Uu]ser_\d+$", k) or k.lower() == "unknown":
                self.user_history.pop(k, None)
                self.last_talk_time.pop(k, None)
                self.talking_now.pop(k, None)
                self.whisper_now.pop(k, None)
                self.last_talk_was_whisper.pop(k, None)
        
        history_enabled = self.config.get("history_enabled", False)
        history_duration = self.config.get("history_duration", 60)
        fade_duration = float(self.config.get("speaker_fade_duration", 5))
        
        changed_channel = False
        prev_cid = getattr(self, 'current_cid', None)
        if my_cid is not None and prev_cid is not None and prev_cid != my_cid:
            self.user_history.clear()
            self.last_talk_time.clear()
            self.talking_now.clear()
            self.whisper_now.clear()
            self.last_talk_was_whisper.clear()
            changed_channel = True
        if my_cid is not None:
            self.current_cid = my_cid

        # Separate channel members from cross-channel (external) whisperers
        channel_clients = [c for c in clients if not c.get("external", False)]
        external_clients = [c for c in clients if c.get("external", False)]
        active_channel_names = {c["name"] for c in channel_clients}
        active_names = {c["name"] for c in clients}

        # Track talking & whisper states and timestamps
        for name in list(self.talking_now.keys()):
            if name not in active_names:
                self.talking_now[name] = False
                self.whisper_now[name] = False

        for c in clients:
            c_name = c["name"]
            is_talking = bool(c.get("talking", False))
            is_external = bool(c.get("external", False))
            is_whisper = is_talking and (bool(c.get("whisper", False)) or is_external)
            self.talking_now[c_name] = is_talking
            self.whisper_now[c_name] = is_whisper
            if is_talking:
                self.last_talk_time[c_name] = current_time
                self.last_talk_was_whisper[c_name] = is_whisper

        prev_external = {
            name: data for name, data in self.user_history.items()
            if data.get("external", False)
        }
        
        was_empty = not any(not d.get("external", False) for d in self.user_history.values())
        is_initial = getattr(self, 'is_initial_snapshot', False) or was_empty or changed_channel
        if channel_clients:
            self.is_initial_snapshot = False

        # Update user history for local channel members
        if history_enabled:
            # Mark new users
            for c in channel_clients:
                name = c["name"]
                if name not in self.user_history or self.user_history[name].get("external", False):
                    # User wasn't in our channel before, they joined now (join_time = 0 on initial snapshot/channel switch so no '+')
                    join_time = 0 if is_initial else current_time
                    self.user_history[name] = {"join_time": join_time, "leave_time": None, "external": False}
                    
                    if not is_initial and self.config.get("tts_enabled", False) and not self.config.get("tts_muted", False) and getattr(self, "is_primary", False):
                        if self.config.get("tts_join_enabled", True):
                            template = self.config.get("tts_join_text", "%NICK joined")
                            from tts_manager import get_tts_manager, apply_tts_aliases
                            from config import clean_nickname
                            spoken_name = apply_tts_aliases(clean_nickname(name, self.config), self.config.get("tts_aliases", {}))
                            text = template.replace("%NICK", spoken_name)
                            delay = self.config.get("tts_delay_ms", 0) / 1000.0
                            voice = self.config.get("tts_voice", "en-US-AriaNeural")
                            rate = self.config.get("tts_rate", "+0%")
                            vol = self.config.get("tts_volume", 80)
                            from tts_manager import get_tts_manager
                            get_tts_manager().enqueue(text, voice=voice, volume=vol, delay=delay, rate=rate)
                else:
                    # User is known, if they previously left, they are back
                    if self.user_history[name]["leave_time"] is not None:
                        # Re-joined! We update join_time and clear leave_time
                        join_time = 0 if is_initial else current_time
                        self.user_history[name] = {"join_time": join_time, "leave_time": None, "external": False}
                        
                        if not is_initial and self.config.get("tts_enabled", False) and not self.config.get("tts_muted", False) and getattr(self, "is_primary", False):
                            if self.config.get("tts_join_enabled", True):
                                template = self.config.get("tts_join_text", "%NICK joined")
                                from tts_manager import get_tts_manager, apply_tts_aliases
                                from config import clean_nickname
                                spoken_name = apply_tts_aliases(clean_nickname(name, self.config), self.config.get("tts_aliases", {}))
                                text = template.replace("%NICK", spoken_name)
                                delay = self.config.get("tts_delay_ms", 0) / 1000.0
                                voice = self.config.get("tts_voice", "en-US-AriaNeural")
                                rate = self.config.get("tts_rate", "+0%")
                                vol = self.config.get("tts_volume", 80)
                                from tts_manager import get_tts_manager
                                get_tts_manager().enqueue(text, voice=voice, volume=vol, delay=delay, rate=rate)
            
            # Mark channel users who left (only when not in an initial snapshot or channel switch)
            if not is_initial:
                for name, data in list(self.user_history.items()):
                    if data.get("external", False):
                        continue
                    if name not in active_channel_names:
                        if data["leave_time"] is None:
                            # User just left
                            data["leave_time"] = current_time
                            
                            if self.config.get("tts_enabled", False) and not self.config.get("tts_muted", False) and getattr(self, "is_primary", False):
                                if self.config.get("tts_leave_enabled", False):
                                    template = self.config.get("tts_leave_text", "%NICK left")
                                    from tts_manager import get_tts_manager, apply_tts_aliases
                                    from config import clean_nickname
                                    spoken_name = apply_tts_aliases(clean_nickname(name, self.config), self.config.get("tts_aliases", {}))
                                    text = template.replace("%NICK", spoken_name)
                                    delay = self.config.get("tts_delay_ms", 0) / 1000.0
                                    voice = self.config.get("tts_voice", "en-US-AriaNeural")
                                    rate = self.config.get("tts_rate", "+0%")
                                    vol = self.config.get("tts_volume", 80)
                                    from tts_manager import get_tts_manager
                                    get_tts_manager().enqueue(text, voice=voice, volume=vol, delay=delay, rate=rate)
                        elif current_time - data["leave_time"] > history_duration:
                            # User left longer than history_duration, remove from history
                            del self.user_history[name]
                            self.last_talk_time.pop(name, None)
                            self.talking_now.pop(name, None)
                            self.whisper_now.pop(name, None)
                            self.last_talk_was_whisper.pop(name, None)
        else:
            # History disabled, match active channel clients + preserve fading external whisperers
            self.user_history = {}
            for c in channel_clients:
                self.user_history[c["name"]] = {"join_time": 0, "leave_time": None, "external": False}
            for name, data in prev_external.items():
                if name not in active_channel_names:
                    self.user_history[name] = data

        # Add active cross-channel (external) whisperers
        for c in external_clients:
            name = c["name"]
            if name in active_channel_names:
                continue
            if c.get("talking", False):
                self.user_history[name] = {"join_time": 0, "leave_time": None, "external": True}

        # Prune external whisperers who stopped whispering and finished speaker_fade_duration
        for name, data in list(self.user_history.items()):
            if not data.get("external", False):
                continue
            if self.talking_now.get(name, False):
                continue
            last_talk = self.last_talk_time.get(name, 0)
            elapsed = current_time - last_talk
            if fade_duration <= 0 or last_talk <= 0 or elapsed >= fade_duration:
                self.user_history.pop(name, None)
                self.last_talk_time.pop(name, None)
                self.talking_now.pop(name, None)
                self.whisper_now.pop(name, None)
                self.last_talk_was_whisper.pop(name, None)

        font_family = self.config.get("font_family", "Sans Serif")
        font_size = self.config.get("font_size", 11)
        cfg_line_height = self.config.get("line_height", 0)
        overlay_font = QFont(font_family, font_size, QFont.Weight.Bold)
        fm = QFontMetrics(overlay_font)
        row_height = cfg_line_height if (cfg_line_height and cfg_line_height > 0) else max(fm.lineSpacing(), 12)
        
        col_normal = self.config.get('text_color_normal', '#96ffffff')
        if col_normal.startswith('rgba'): col_normal = '#96ffffff'
        col_talking = self.config.get('text_color_talking', '#00FFCC')
        if col_talking.startswith('rgba'): col_talking = '#00FFCC'
        col_whisper = self.config.get('text_color_whisper', '#ff9900')
        if col_whisper.startswith('rgba'): col_whisper = '#ff9900'
        col_left = self.config.get('text_color_left', '#808080')
        if col_left.startswith('rgba'): col_left = '#808080'

        from config import clean_nickname

        sort_mode = self.config.get("sort_order")
        if not sort_mode or sort_mode == "voice":
            sort_mode = "recent_speakers" if self.config.get("recent_speakers_first", False) else "alphabetical_fading_top"

        # Build ordered list of names to display
        display_names = list(self.user_history.keys())
            
        # We need to sort: active first, then left users always at the bottom
        def sort_key(name):
            data = self.user_history.get(name, {})
            is_left = data.get("leave_time") is not None
            cleaned = clean_nickname(name, self.config).lower()

            # Rule: Always place users who left the channel at the bottom
            if is_left:
                leave_t = data.get("leave_time", 0) or 0
                return (99, -leave_t, cleaned)

            if sort_mode == "recent_speakers":
                # Speaking order: most recent on top
                last_talk = self.last_talk_time.get(name, 0)
                if last_talk > 0:
                    return (0, -last_talk, cleaned)
                else:
                    return (1, cleaned)

            elif sort_mode == "alphabetical":
                # Alphabetical: speakers stay in-place within the list
                return (0, cleaned)

            elif sort_mode == "alphabetical_fading_top":
                # Alphabetical: recent speakers on top while talking or fading, then fall back alphabetically
                is_talking = self.talking_now.get(name, False)
                last_talk = self.last_talk_time.get(name, 0)
                elapsed = current_time - last_talk if last_talk > 0 else 999999
                is_recent_fading = is_talking or (fade_duration > 0 and last_talk > 0 and elapsed < fade_duration)
                
                if is_recent_fading:
                    return (0, -last_talk, cleaned)
                else:
                    return (1, cleaned)

            return (0, cleaned)
            
        display_names.sort(key=sort_key)

        # Separate active and left users so list limit only trims active users
        active_display_names = [n for n in display_names if self.user_history[n]["leave_time"] is None]
        left_display_names = [n for n in display_names if self.user_history[n]["leave_time"] is not None]

        # Limit user list if enabled (trims active users, users who left are always preserved at the bottom)
        if self.config.get("limit_users_enabled", False):
            try:
                limit_count = int(str(self.config.get("limit_users_count", "10")).strip())
                if limit_count > 0:
                    active_display_names = active_display_names[:limit_count]
            except ValueError:
                pass
        
        display_names = active_display_names + left_display_names
        
        # Remove old labels not in display_names
        to_remove = []
        for name, lbl in self.labels.items():
            if name not in display_names:
                self.users_container.removeWidget(lbl)
                lbl.hide()
                lbl.setParent(None)
                lbl.deleteLater()
                to_remove.append(name)
                
        for name in to_remove:
            del self.labels[name]
            
        # Rebuild/update labels
        for name in display_names:
            data = self.user_history[name]
            is_left = data["leave_time"] is not None
            is_external_user = data.get("external", False)
            is_new = history_enabled and not is_left and not is_external_user and (current_time - data["join_time"] < history_duration)
            
            # Format text
            from config import clean_nickname
            clean_name = clean_nickname(name, self.config)
            arrow_text = ""
            if is_left:
                arrow_text = "🡇"
            elif is_new:
                arrow_text = "🡅"
                
            # Get talking state
            talking = self.talking_now.get(name, False)
            last_talk = self.last_talk_time.get(name, 0)
            elapsed = current_time - last_talk
            
            # Create or update label
            if name not in self.labels:
                lbl = UserRowWidget(self)
                lbl.setFont(overlay_font)
                lbl.setFixedHeight(row_height)
                self.labels[name] = lbl
            else:
                lbl = self.labels[name]
                lbl.setFont(overlay_font)
                lbl.setFixedHeight(row_height)
                
            lbl.set_content(clean_name, arrow_text)
            lbl.setVisible(True)
                
            # Remove from layout and re-add to enforce order
            self.users_container.removeWidget(lbl)
            self.users_container.addWidget(lbl)
            
            # Apply style
            if is_left:
                lbl.setStyleSheet(f"color: {col_left}; background-color: transparent; border: none;")
            elif talking:
                active_col = col_whisper if self.whisper_now.get(name, False) else col_talking
                lbl.setStyleSheet(f"color: {active_col}; background-color: transparent; border: none;")
            elif fade_duration > 0 and last_talk > 0 and elapsed < fade_duration:
                progress = elapsed / fade_duration
                from_col = col_whisper if self.last_talk_was_whisper.get(name, False) else col_talking
                col = interpolate_color(from_col, col_normal, progress)
                lbl.setStyleSheet(f"color: {col}; background-color: transparent; border: none;")
            else:
                lbl.setStyleSheet(f"color: {col_normal}; background-color: transparent; border: none;")

        # Start fade timer if any user is currently fading
        if fade_duration > 0:
            any_fading = any(
                not self.talking_now.get(name, False) and (0 < self.last_talk_time.get(name, 0) and (current_time - self.last_talk_time.get(name, 0) < fade_duration))
                for name in display_names
                if self.user_history.get(name, {}).get("leave_time") is None
            )
            if any_fading and not self.fade_timer.isActive():
                self.fade_timer.start(40)

        self._update_overlay_geometry()

    # Mouse events for dragging when in move mode
    def mousePressEvent(self, event):
        if self.move_mode and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.drag_start_pos = event.globalPosition().toPoint()
            self.window_start_pos = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.move_mode and (event.buttons() & Qt.MouseButton.LeftButton):
            if hasattr(self, 'drag_start_pos') and hasattr(self, 'window_start_pos'):
                delta = event.globalPosition().toPoint() - self.drag_start_pos
                if delta.manhattanLength() > 0:
                    self._user_moved = True
                self.move(self.window_start_pos + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.move_mode and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if getattr(self, '_user_moved', False):
                if "overlay_ids" not in self.config:
                    self.config["overlay_ids"] = {}
                if self.overlay_id not in self.config["overlay_ids"]:
                    self.config["overlay_ids"][self.overlay_id] = {}
                    
                new_x, new_y = self._sanitize_position(self.pos().x(), self.pos().y(), self.width())
                if new_x != self.pos().x() or new_y != self.pos().y():
                    self.move(new_x, new_y)
                self.config["overlay_ids"][self.overlay_id]["pos_x"] = new_x
                self.config["overlay_ids"][self.overlay_id]["pos_y"] = new_y
                self.config["overlay_ids"][self.overlay_id]["pos_right"] = new_x + self.width()
                if hasattr(self, 'save_callback') and self.save_callback:
                    self.save_callback()
            event.accept()
