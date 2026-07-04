from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QSlider, QCheckBox
from PyQt6.QtCore import Qt

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
        
        # Opacity Slider (Normal)
        self.opacity_normal_label = QLabel("Background Opacity (Normal Mode):")
        self.opacity_normal_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_normal_slider.setMinimum(0)
        self.opacity_normal_slider.setMaximum(100)
        self.opacity_normal_slider.setValue(int(self.config.get("opacity_normal", 0.0) * 100))
        layout.addWidget(self.opacity_normal_label)
        layout.addWidget(self.opacity_normal_slider)
        
        # Opacity Slider (Moving)
        self.opacity_move_label = QLabel("Background Opacity (When Moving):")
        self.opacity_move_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_move_slider.setMinimum(0)
        self.opacity_move_slider.setMaximum(100)
        # Migrate old "opacity" if it exists, otherwise 0.8
        self.opacity_move_slider.setValue(int(self.config.get("opacity", self.config.get("opacity_move", 0.8)) * 100))
        layout.addWidget(self.opacity_move_label)
        layout.addWidget(self.opacity_move_slider)

        # Show Header Checkbox
        self.header_checkbox = QCheckBox("Show Title Header")
        self.header_checkbox.setChecked(self.config.get("show_header", True))
        layout.addWidget(self.header_checkbox)
        
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
        
    def get_updated_config(self):
        new_config = dict(self.config)
        new_config["api_key"] = self.api_key_input.text().strip()
        new_config["opacity_normal"] = self.opacity_normal_slider.value() / 100.0
        new_config["opacity_move"] = self.opacity_move_slider.value() / 100.0
        if "opacity" in new_config:
            del new_config["opacity"]
        new_config["show_header"] = self.header_checkbox.isChecked()
        return new_config
