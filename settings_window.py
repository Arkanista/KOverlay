from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QSlider, QCheckBox, QFontComboBox, QSpinBox, QColorDialog, QGroupBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

class SettingsWindow(QDialog):
    config_changed = pyqtSignal()

    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KOverlay Settings")
        self.setMinimumWidth(400)
        
        self.config = current_config
        
        layout = QVBoxLayout()
        
        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_key_input.setPlaceholderText("Enter TS3 Client API Key here")
        self.api_key_input.editingFinished.connect(self._on_change)
        layout.addWidget(QLabel("TS3 API Key:"))
        layout.addWidget(self.api_key_input)
        
        # Show Only in Game
        self.game_only_checkbox = QCheckBox("Show ONLY when game is active")
        self.game_only_checkbox.setChecked(self.config.get("game_only", True))
        self.game_only_checkbox.toggled.connect(self._on_change)
        layout.addWidget(self.game_only_checkbox)

        # Hide Delay
        delay_layout = QHBoxLayout()
        self.hide_delay_checkbox = QCheckBox("Delay hiding when game loses focus")
        self.hide_delay_checkbox.setChecked(self.config.get("hide_delay_enabled", False))
        self.hide_delay_checkbox.toggled.connect(self._on_change)
        
        self.hide_delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.hide_delay_slider.setRange(1, 60)
        self.hide_delay_slider.setValue(self.config.get("hide_delay_seconds", 5))
        self.hide_delay_val_label = QLabel(f"{self.hide_delay_slider.value()}s")
        self.hide_delay_slider.valueChanged.connect(lambda v: self.hide_delay_val_label.setText(f"{v}s"))
        self.hide_delay_slider.valueChanged.connect(self._on_change)
        
        self.hide_delay_slider.setEnabled(self.hide_delay_checkbox.isChecked())
        self.hide_delay_checkbox.toggled.connect(self.hide_delay_slider.setEnabled)
        
        delay_layout.addWidget(self.hide_delay_checkbox)
        delay_layout.addWidget(self.hide_delay_slider)
        delay_layout.addWidget(self.hide_delay_val_label)
        layout.addLayout(delay_layout)

        # Target Keywords
        self.keywords_input = QLineEdit()
        current_keywords = self.config.get("target_keywords", ["EVE - ", "exefile.exe"])
        self.keywords_input.setText(", ".join(current_keywords))
        self.keywords_input.setPlaceholderText("e.g. EVE - , exefile.exe")
        self.keywords_input.editingFinished.connect(self._on_change)
        layout.addWidget(QLabel("Target Window Keywords (comma separated):"))
        layout.addWidget(self.keywords_input)
        
        # History
        self.history_group = QGroupBox("Join/Leave History")
        history_layout = QVBoxLayout()
        
        self.history_checkbox = QCheckBox("Enable Join/Leave History (+ / ✝ indicators)")
        self.history_checkbox.setChecked(self.config.get("history_enabled", False))
        self.history_checkbox.toggled.connect(self._on_change)
        history_layout.addWidget(self.history_checkbox)
        
        history_dur_layout = QHBoxLayout()
        self.history_dur_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_dur_slider.setRange(1, 300)
        self.history_dur_slider.setValue(self.config.get("history_duration", 60))
        self.history_dur_val_label = QLabel(f"{self.history_dur_slider.value()}s")
        self.history_dur_slider.valueChanged.connect(lambda v: self.history_dur_val_label.setText(f"{v}s"))
        self.history_dur_slider.valueChanged.connect(self._on_change)
        
        self.history_dur_slider.setEnabled(self.history_checkbox.isChecked())
        self.history_checkbox.toggled.connect(self.history_dur_slider.setEnabled)
        
        history_dur_layout.addWidget(QLabel("Duration:"))
        history_dur_layout.addWidget(self.history_dur_slider)
        history_dur_layout.addWidget(self.history_dur_val_label)
        history_layout.addLayout(history_dur_layout)
        
        self.history_group.setLayout(history_layout)
        layout.addWidget(self.history_group)

        
        # Polling Interval Slider
        poll_layout = QHBoxLayout()
        self.poll_label = QLabel("Active Window Check Interval:")
        self.poll_slider = QSlider(Qt.Orientation.Horizontal)
        self.poll_slider.setMinimum(50)
        self.poll_slider.setMaximum(1000)
        self.poll_slider.setSingleStep(50)
        self.poll_slider.setTickInterval(50)
        self.poll_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        # Enforce step of 50 manually using valueChanged
        def on_poll_slider_changed(val):
            snapped = round(val / 50) * 50
            if snapped != val:
                self.poll_slider.blockSignals(True)
                self.poll_slider.setValue(snapped)
                self.poll_slider.blockSignals(False)
            self.poll_val_label.setText(f"{snapped} ms")
            self._on_change()
            
        self.poll_slider.valueChanged.connect(on_poll_slider_changed)
        
        current_poll = self.config.get("polling_interval_ms", 50)
        self.poll_val_label = QLabel(f"{current_poll} ms")
        self.poll_val_label.setMinimumWidth(60)
        self.poll_slider.blockSignals(True)
        self.poll_slider.setValue(current_poll)
        self.poll_slider.blockSignals(False)
        
        poll_layout.addWidget(self.poll_label)
        poll_layout.addWidget(self.poll_slider)
        poll_layout.addWidget(self.poll_val_label)
        layout.addLayout(poll_layout)
        
        # TTS Settings
        import importlib.util
        import shutil
        edge_tts_installed = importlib.util.find_spec("edge_tts") is not None
        mpv_installed = shutil.which("mpv") is not None
        tts_available = edge_tts_installed and mpv_installed
        
        self.tts_group = QGroupBox("Text-to-Speech (TTS)")
        tts_layout = QVBoxLayout()
        
        self.tts_checkbox = QCheckBox("Enable TTS Voice Announcements (English)")
        self.tts_checkbox.setChecked(self.config.get("tts_enabled", False))
        
        if not tts_available:
            self.tts_checkbox.setChecked(False)
            self.tts_checkbox.setEnabled(False)
            self.config["tts_enabled"] = False
            self.tts_checkbox.setText("Enable TTS Announcements (Unavailable)")
            
        self.tts_checkbox.toggled.connect(self._on_change)
        tts_layout.addWidget(self.tts_checkbox)
        
        info_label = QLabel("Note: Uses the internet for high-quality voices. Requires 'edge-tts' Python module and 'mpv' player.")
        font = info_label.font()
        font.setPointSize(font.pointSize() - 2)
        info_label.setFont(font)
        info_label.setStyleSheet("color: gray;")
        info_label.setWordWrap(True)
        tts_layout.addWidget(info_label)
        
        tts_delay_layout = QHBoxLayout()
        self.tts_delay_label = QLabel("Read Delay:")
        self.tts_delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_delay_slider.setMinimum(0)
        self.tts_delay_slider.setMaximum(3000)
        self.tts_delay_slider.setSingleStep(250)
        self.tts_delay_slider.setTickInterval(250)
        self.tts_delay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        def on_tts_slider_changed(val):
            snapped = round(val / 250) * 250
            if snapped != val:
                self.tts_delay_slider.blockSignals(True)
                self.tts_delay_slider.setValue(snapped)
                self.tts_delay_slider.blockSignals(False)
            self.tts_delay_val_label.setText(f"{snapped} ms")
            self._on_change()
            
        self.tts_delay_slider.valueChanged.connect(on_tts_slider_changed)
        
        current_tts_delay = self.config.get("tts_delay_ms", 0)
        self.tts_delay_val_label = QLabel(f"{current_tts_delay} ms")
        self.tts_delay_val_label.setMinimumWidth(60)
        self.tts_delay_slider.blockSignals(True)
        self.tts_delay_slider.setValue(current_tts_delay)
        self.tts_delay_slider.blockSignals(False)
        
        self.tts_delay_slider.setEnabled(self.tts_checkbox.isChecked())
        self.tts_checkbox.toggled.connect(self.tts_delay_slider.setEnabled)
        
        tts_delay_layout.addWidget(self.tts_delay_label)
        tts_delay_layout.addWidget(self.tts_delay_slider)
        tts_delay_layout.addWidget(self.tts_delay_val_label)
        tts_layout.addLayout(tts_delay_layout)
        
        self.tts_group.setLayout(tts_layout)
        layout.addWidget(self.tts_group)
        
        # Overlays
        self.monitors_group = QGroupBox("Overlays")
        monitors_layout = QVBoxLayout()
        self.monitor_checkboxes = {}
        for index in range(1, 5):
            overlay_id = str(index)
            mon_cfg = self.config.get("overlay_ids", {}).get(overlay_id, {})
            
            cb = QCheckBox(f"Enable Overlay {overlay_id}")
            cb.setChecked(mon_cfg.get("enabled", False))
            cb.toggled.connect(self._on_change)
            self.monitor_checkboxes[overlay_id] = cb
            monitors_layout.addWidget(cb)
            
        self.monitors_group.setLayout(monitors_layout)
        layout.addWidget(self.monitors_group)

        # Width Settings
        width_layout = QHBoxLayout()
        self.dynamic_width_checkbox = QCheckBox("Dynamic Width (fit to text)")
        self.dynamic_width_checkbox.setChecked(self.config.get("dynamic_width", True))
        self.dynamic_width_checkbox.toggled.connect(self._on_change)
        
        self.fixed_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.fixed_width_slider.setRange(50, 1000)
        self.fixed_width_slider.setValue(self.config.get("fixed_width", 200))
        self.fixed_width_val_label = QLabel(f"{self.fixed_width_slider.value()}px")
        self.fixed_width_slider.valueChanged.connect(lambda v: self.fixed_width_val_label.setText(f"{v}px"))
        self.fixed_width_slider.valueChanged.connect(self._on_change)
        
        self.fixed_width_slider.setEnabled(not self.dynamic_width_checkbox.isChecked())
        self.dynamic_width_checkbox.toggled.connect(lambda checked: self.fixed_width_slider.setEnabled(not checked))
        
        width_layout.addWidget(self.dynamic_width_checkbox)
        width_layout.addWidget(QLabel("Fixed Width:"))
        width_layout.addWidget(self.fixed_width_slider)
        width_layout.addWidget(self.fixed_width_val_label)
        layout.addLayout(width_layout)

        # Opacity Slider (Normal)
        normal_layout = QHBoxLayout()
        self.opacity_normal_label = QLabel("Background Opacity (Normal Mode):")
        self.opacity_normal_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_normal_slider.setRange(0, 100)
        self.opacity_normal_slider.setValue(int(self.config.get("opacity_normal", 0.0) * 100))
        self.opacity_normal_slider.valueChanged.connect(self._update_opacity_normal_label)
        self.opacity_normal_slider.valueChanged.connect(self._on_change)
        self.opacity_normal_val_label = QLabel(f"{self.opacity_normal_slider.value()}%")
        normal_layout.addWidget(self.opacity_normal_label)
        normal_layout.addWidget(self.opacity_normal_slider)
        normal_layout.addWidget(self.opacity_normal_val_label)
        layout.addLayout(normal_layout)
        
        # Opacity Slider (Move Mode)
        move_layout = QHBoxLayout()
        self.opacity_move_label = QLabel("Background Opacity (Move Mode):")
        self.opacity_move_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_move_slider.setRange(0, 100)
        self.opacity_move_slider.setValue(int(self.config.get("opacity_move", self.config.get("opacity", 0.8)) * 100))
        self.opacity_move_slider.valueChanged.connect(self._update_opacity_move_label)
        self.opacity_move_slider.valueChanged.connect(self._on_change)
        self.opacity_move_val_label = QLabel(f"{self.opacity_move_slider.value()}%")
        move_layout.addWidget(self.opacity_move_label)
        move_layout.addWidget(self.opacity_move_slider)
        move_layout.addWidget(self.opacity_move_val_label)
        layout.addLayout(move_layout)

        # Font settings
        font_layout = QHBoxLayout()
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.config.get("font_family", "Sans Serif")))
        self.font_combo.currentFontChanged.connect(self._on_change)
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(self.config.get("font_size", 11))
        self.font_size.valueChanged.connect(self._on_change)
        font_layout.addWidget(QLabel("Font:"))
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(QLabel("Size:"))
        font_layout.addWidget(self.font_size)
        layout.addLayout(font_layout)

        # Color Buttons
        color_layout = QHBoxLayout()
        self.color_btn = QPushButton("Choose Background Color")
        self.current_bg_color = self.config.get("bg_color", "#000000")
        self._update_color_btn()
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_btn)
        
        self.text_color_normal_btn = QPushButton("Choose Text Color (Normal)")
        val_normal = self.config.get("text_color_normal", "#96ffffff")
        if val_normal.startswith("rgba"): val_normal = "#96ffffff"
        self.current_text_color_normal = val_normal
        self._update_text_color_normal_btn()
        self.text_color_normal_btn.clicked.connect(self._choose_text_color_normal)
        color_layout.addWidget(self.text_color_normal_btn)
        
        self.text_color_talking_btn = QPushButton("Choose Text Color (Talking)")
        val_talking = self.config.get("text_color_talking", "#00ffcc")
        if val_talking.startswith("rgba"): val_talking = "#00ffcc"
        self.current_text_color_talking = val_talking
        self._update_text_color_talking_btn()
        self.text_color_talking_btn.clicked.connect(self._choose_text_color_talking)
        color_layout.addWidget(self.text_color_talking_btn)
        
        self.text_color_left_btn = QPushButton("Choose Text Color (Left)")
        val_left = self.config.get("text_color_left", "#808080")
        if val_left.startswith("rgba"): val_left = "#808080"
        self.current_text_color_left = val_left
        self._update_text_color_left_btn()
        self.text_color_left_btn.clicked.connect(self._choose_text_color_left)
        color_layout.addWidget(self.text_color_left_btn)
        
        layout.addLayout(color_layout)

        # Show Header Checkbox
        self.header_checkbox = QCheckBox("Show Title Header (Logo + Text)")
        self.header_checkbox.setChecked(self.config.get("show_header", True))
        self.header_checkbox.toggled.connect(self._on_change)
        layout.addWidget(self.header_checkbox)
        
        # Show Three Dots Checkbox
        self.three_dots_checkbox = QCheckBox("Show Dots Indicator (number of dots indicates ID number of overlay)")
        self.three_dots_checkbox.setChecked(self.config.get("show_three_dots", False))
        self.three_dots_checkbox.toggled.connect(self._on_change)
        layout.addWidget(self.three_dots_checkbox)
        
        # Disable Blink
        self.disable_blink_checkbox = QCheckBox("Disable border blinking on startup")
        self.disable_blink_checkbox.setChecked(self.config.get("disable_blink", False))
        self.disable_blink_checkbox.toggled.connect(self._on_change)
        layout.addWidget(self.disable_blink_checkbox)
        
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Close")
        self.save_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.save_btn)
        
        layout.addStretch()
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def _update_opacity_normal_label(self, val):
        self.opacity_normal_val_label.setText(f"{val}%")

    def _update_opacity_move_label(self, val):
        self.opacity_move_val_label.setText(f"{val}%")

    def _update_color_btn(self):
        c = QColor(self.current_bg_color)
        text_col = 'white' if c.lightness() < 128 else 'black'
        self.color_btn.setStyleSheet(f"background-color: {self.current_bg_color}; color: {text_col};")

    def _update_text_color_normal_btn(self):
        c = QColor(self.current_text_color_normal)
        text_col = 'white' if c.lightness() < 128 else 'black'
        # Need to strip rgba/alpha for background if it has it, but it's fine
        self.text_color_normal_btn.setStyleSheet(f"background-color: {self.current_text_color_normal}; color: {text_col};")

    def _update_text_color_talking_btn(self):
        c = QColor(self.current_text_color_talking)
        text_col = 'white' if c.lightness() < 128 else 'black'
        self.text_color_talking_btn.setStyleSheet(f"background-color: {self.current_text_color_talking}; color: {text_col};")

    def _update_text_color_left_btn(self):
        c = QColor(self.current_text_color_left)
        text_col = 'white' if c.lightness() < 128 else 'black'
        self.text_color_left_btn.setStyleSheet(f"background-color: {self.current_text_color_left}; color: {text_col};")

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_bg_color), self, "Select Background Color", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_bg_color = color.name(QColor.NameFormat.HexArgb)
            self._update_color_btn()
            self._on_change()
            
    def _choose_text_color_normal(self):
        color = QColorDialog.getColor(QColor(self.current_text_color_normal), self, "Select Text Color (Normal)", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_text_color_normal = color.name(QColor.NameFormat.HexArgb)
            self._update_text_color_normal_btn()
            self._on_change()
            
    def _choose_text_color_talking(self):
        color = QColorDialog.getColor(QColor(self.current_text_color_talking), self, "Select Text Color (Talking)", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_text_color_talking = color.name(QColor.NameFormat.HexArgb)
            self._update_text_color_talking_btn()
            self._on_change()
            
    def _choose_text_color_left(self):
        color = QColorDialog.getColor(QColor(self.current_text_color_left), self, "Select Text Color (Left)", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_text_color_left = color.name(QColor.NameFormat.HexArgb)
            self._update_text_color_left_btn()
            self._on_change()
            
    def _on_change(self):
        if not hasattr(self, 'monitor_checkboxes'):
            return
            
        # Update config directly
        if "overlay_ids" not in self.config:
            self.config["overlay_ids"] = {}
        for o_id, cb in self.monitor_checkboxes.items():
            if o_id not in self.config["overlay_ids"]:
                self.config["overlay_ids"][o_id] = {}
            self.config["overlay_ids"][o_id]["enabled"] = cb.isChecked()
            
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["game_only"] = self.game_only_checkbox.isChecked()
        self.config["hide_delay_enabled"] = self.hide_delay_checkbox.isChecked()
        self.config["hide_delay_seconds"] = self.hide_delay_slider.value()
        self.config["target_keywords"] = [k.strip() for k in self.keywords_input.text().split(",") if k.strip()]
        self.config["polling_interval_ms"] = self.poll_slider.value()
        self.config["opacity_normal"] = self.opacity_normal_slider.value() / 100.0
        self.config["opacity_move"] = self.opacity_move_slider.value() / 100.0
        self.config["dynamic_width"] = self.dynamic_width_checkbox.isChecked()
        self.config["fixed_width"] = self.fixed_width_slider.value()
        if "opacity" in self.config:
            del self.config["opacity"]
        self.config["font_family"] = self.font_combo.currentFont().family()
        self.config["font_size"] = self.font_size.value()
        self.config["bg_color"] = self.current_bg_color
        self.config["text_color_normal"] = self.current_text_color_normal
        self.config["text_color_talking"] = self.current_text_color_talking
        self.config["text_color_left"] = self.current_text_color_left
        self.config["show_header"] = self.header_checkbox.isChecked()
        self.config["show_three_dots"] = self.three_dots_checkbox.isChecked()
        self.config["disable_blink"] = self.disable_blink_checkbox.isChecked()
        self.config["history_enabled"] = self.history_checkbox.isChecked()
        self.config["tts_enabled"] = self.tts_checkbox.isChecked()
        self.config["tts_delay_ms"] = self.tts_delay_slider.value()
        self.config["history_duration"] = self.history_dur_slider.value()
        
        # Emit signal to inform main app to apply changes
        self.config_changed.emit()
