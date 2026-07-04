from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QSlider, QCheckBox, QFontComboBox, QSpinBox, QColorDialog, QGroupBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

class SettingsWindow(QDialog):
    config_changed = pyqtSignal()

    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TS3 Overlay Settings")
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
        self.game_only_checkbox = QCheckBox("Show ONLY when EVE is active")
        self.game_only_checkbox.setChecked(self.config.get("game_only", True))
        self.game_only_checkbox.toggled.connect(self._on_change)
        layout.addWidget(self.game_only_checkbox)

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

        # Background Color Button
        color_layout = QHBoxLayout()
        self.color_btn = QPushButton("Choose Background Color")
        self.current_bg_color = self.config.get("bg_color", "#000000")
        self._update_color_btn()
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_btn)
        layout.addLayout(color_layout)

        # Show Header Checkbox
        self.header_checkbox = QCheckBox("Show Title Header (Logo + Text)")
        self.header_checkbox.setChecked(self.config.get("show_header", True))
        self.header_checkbox.toggled.connect(self._on_change)
        layout.addWidget(self.header_checkbox)
        
        # Show Three Dots Checkbox
        self.three_dots_checkbox = QCheckBox("Show Dots Indicator (Compact Mode)")
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

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_bg_color), self, "Select Background Color")
        if color.isValid():
            self.current_bg_color = color.name()
            self._update_color_btn()
            self._on_change()
            
    def _on_change(self):
        # Update config directly
        if "overlay_ids" not in self.config:
            self.config["overlay_ids"] = {}
        for o_id, cb in self.monitor_checkboxes.items():
            if o_id not in self.config["overlay_ids"]:
                self.config["overlay_ids"][o_id] = {}
            self.config["overlay_ids"][o_id]["enabled"] = cb.isChecked()
            
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["game_only"] = self.game_only_checkbox.isChecked()
        self.config["opacity_normal"] = self.opacity_normal_slider.value() / 100.0
        self.config["opacity_move"] = self.opacity_move_slider.value() / 100.0
        self.config["dynamic_width"] = self.dynamic_width_checkbox.isChecked()
        self.config["fixed_width"] = self.fixed_width_slider.value()
        if "opacity" in self.config:
            del self.config["opacity"]
        self.config["font_family"] = self.font_combo.currentFont().family()
        self.config["font_size"] = self.font_size.value()
        self.config["bg_color"] = self.current_bg_color
        self.config["show_header"] = self.header_checkbox.isChecked()
        self.config["show_three_dots"] = self.three_dots_checkbox.isChecked()
        self.config["disable_blink"] = self.disable_blink_checkbox.isChecked()
        
        # Emit signal to inform main app to apply changes
        self.config_changed.emit()
