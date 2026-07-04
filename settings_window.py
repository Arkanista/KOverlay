from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QSlider, QCheckBox, QFontComboBox, QSpinBox, QColorDialog, QGroupBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication
import copy

class SettingsWindow(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TS3 Overlay Settings")
        self.setMinimumWidth(400)
        
        self.config = current_config
        
        layout = QVBoxLayout()
        
        # API Key
        self.api_key_label = QLabel("ClientQuery API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_key_input.setPlaceholderText("e.g. 41CT-14L3-...")
        layout.addWidget(self.api_key_label)
        layout.addWidget(self.api_key_input)
        
        # Show Only in Game
        self.game_only_checkbox = QCheckBox("Show ONLY when EVE is active")
        self.game_only_checkbox.setChecked(self.config.get("game_only", True))
        layout.addWidget(self.game_only_checkbox)

        # Monitors
        self.monitors_group = QGroupBox("Monitor Layout & Overlays")
        monitors_layout = QVBoxLayout()
        self.monitor_checkboxes = {}
        for screen in QGuiApplication.screens():
            s_name = screen.name()
            s_geom = screen.geometry()
            mon_cfg = self.config.get("monitors", {}).get(s_name, {})
            
            cb = QCheckBox(f"{s_name} ({s_geom.width()}x{s_geom.height()})")
            cb.setChecked(mon_cfg.get("enabled", False))
            self.monitor_checkboxes[s_name] = cb
            monitors_layout.addWidget(cb)
            
        self.monitors_group.setLayout(monitors_layout)
        layout.addWidget(self.monitors_group)

        # Opacity Slider (Normal)
        normal_layout = QHBoxLayout()
        self.opacity_normal_label = QLabel("Background Opacity (Normal Mode):")
        self.opacity_normal_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_normal_slider.setMinimum(0)
        self.opacity_normal_slider.setMaximum(100)
        self.opacity_normal_slider.setValue(int(self.config.get("opacity_normal", 0.0) * 100))
        self.opacity_normal_val = QLabel(f"{self.opacity_normal_slider.value()}%")
        self.opacity_normal_slider.valueChanged.connect(lambda v: self.opacity_normal_val.setText(f"{v}%"))
        normal_layout.addWidget(self.opacity_normal_label)
        normal_layout.addWidget(self.opacity_normal_slider)
        normal_layout.addWidget(self.opacity_normal_val)
        layout.addLayout(normal_layout)
        
        # Opacity Slider (Moving)
        move_layout = QHBoxLayout()
        self.opacity_move_label = QLabel("Background Opacity (When Moving):")
        self.opacity_move_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_move_slider.setMinimum(0)
        self.opacity_move_slider.setMaximum(100)
        # Migrate old "opacity" if it exists, otherwise 0.8
        self.opacity_move_slider.setValue(int(self.config.get("opacity", self.config.get("opacity_move", 0.8)) * 100))
        self.opacity_move_val = QLabel(f"{self.opacity_move_slider.value()}%")
        self.opacity_move_slider.valueChanged.connect(lambda v: self.opacity_move_val.setText(f"{v}%"))
        move_layout.addWidget(self.opacity_move_label)
        move_layout.addWidget(self.opacity_move_slider)
        move_layout.addWidget(self.opacity_move_val)
        layout.addLayout(move_layout)

        # Font Selection
        font_layout = QHBoxLayout()
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.config.get("font_family", "Sans Serif")))
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(self.config.get("font_size", 11))
        font_layout.addWidget(QLabel("Font:"))
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(self.font_size)
        layout.addLayout(font_layout)

        # Background Color
        color_layout = QHBoxLayout()
        self.bg_color_btn = QPushButton("Select Background Color")
        self.current_bg_color = self.config.get("bg_color", "#000000")
        self._update_color_btn()
        self.bg_color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(QLabel("Background Color:"))
        color_layout.addWidget(self.bg_color_btn)
        layout.addLayout(color_layout)

        # Show Header Checkbox
        self.header_checkbox = QCheckBox("Show Title Header")
        self.header_checkbox.setChecked(self.config.get("show_header", True))
        layout.addWidget(self.header_checkbox)
        
        # Show Three Dots Checkbox
        self.three_dots_checkbox = QCheckBox("Show '•••' in header")
        self.three_dots_checkbox.setChecked(self.config.get("show_three_dots", False))
        layout.addWidget(self.three_dots_checkbox)
        
        # Connect to parent checkbox
        self.header_checkbox.toggled.connect(self.three_dots_checkbox.setEnabled)
        self.three_dots_checkbox.setEnabled(self.header_checkbox.isChecked())
        
        # Disable Blink
        self.disable_blink_checkbox = QCheckBox("Disable border blinking on startup")
        self.disable_blink_checkbox.setChecked(self.config.get("disable_blink", False))
        layout.addWidget(self.disable_blink_checkbox)
        
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addStretch()
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def _update_color_btn(self):
        c = QColor(self.current_bg_color)
        text_col = 'white' if c.lightness() < 128 else 'black'
        self.bg_color_btn.setStyleSheet(f"background-color: {self.current_bg_color}; color: {text_col};")

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_bg_color), self, "Select Background Color")
        if color.isValid():
            self.current_bg_color = color.name()
            self._update_color_btn()
        
    def get_updated_config(self):
        new_config = copy.deepcopy(self.config)
        
        # Save monitors
        if "monitors" not in new_config:
            new_config["monitors"] = {}
        for s_name, cb in self.monitor_checkboxes.items():
            if s_name not in new_config["monitors"]:
                new_config["monitors"][s_name] = {}
            new_config["monitors"][s_name]["enabled"] = cb.isChecked()
            
        new_config["api_key"] = self.api_key_input.text().strip()
        new_config["game_only"] = self.game_only_checkbox.isChecked()
        new_config["opacity_normal"] = self.opacity_normal_slider.value() / 100.0
        new_config["opacity_move"] = self.opacity_move_slider.value() / 100.0
        if "opacity" in new_config:
            del new_config["opacity"]
        new_config["font_family"] = self.font_combo.currentFont().family()
        new_config["font_size"] = self.font_size.value()
        new_config["bg_color"] = self.current_bg_color
        new_config["show_header"] = self.header_checkbox.isChecked()
        new_config["show_three_dots"] = self.three_dots_checkbox.isChecked()
        new_config["disable_blink"] = self.disable_blink_checkbox.isChecked()
        return new_config
