from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QSlider, QCheckBox, QFontComboBox, QSpinBox, QColorDialog, QGroupBox, QComboBox, QScrollArea, QWidget, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QEvent, QRegularExpression, QUrl
from PyQt6.QtGui import QColor, QFont, QRegularExpressionValidator, QDesktopServices

class ScrollFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if not obj.hasFocus():
                event.ignore()
                return True
        return super().eventFilter(obj, event)

class SettingsWindow(QDialog):
    config_changed = pyqtSignal()

    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KOverlay Settings")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedWidth(1000)
        self.setMaximumHeight(768)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(130, 130, 130, 0.4);
                border-radius: 4px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                font-weight: bold;
                font-size: 12pt;
            }
        """)
        
        self.config = current_config
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.container_widget = QWidget()
        layout = QVBoxLayout(self.container_widget)
        
        # General Settings Group
        self.general_group = QGroupBox("General settings")
        general_group_layout = QVBoxLayout()
        
        # API Key and Target Keywords
        general_layout = QHBoxLayout()
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_key_input.setPlaceholderText("Enter TS3 API Key here")
        self.api_key_input.editingFinished.connect(self._on_change)
        general_layout.addWidget(QLabel("TS3 API Key:"))
        general_layout.addWidget(self.api_key_input)
        
        general_layout.addSpacing(20)
        
        self.keywords_input = QLineEdit()
        current_keywords = self.config.get("target_keywords", ["EVE - ", "exefile.exe"])
        self.keywords_input.setText(", ".join(current_keywords))
        self.keywords_input.setPlaceholderText("e.g. EVE - , exefile.exe")
        self.keywords_input.editingFinished.connect(self._on_change)
        general_layout.addWidget(QLabel("Target Window Keywords (comma separated):"))
        general_layout.addWidget(self.keywords_input)
        
        general_group_layout.addLayout(general_layout)
        
        # Show Only in Game & Hide Delay
        delay_layout = QHBoxLayout()
        self.game_only_checkbox = QCheckBox("Show ONLY when game is active")
        self.game_only_checkbox.setChecked(self.config.get("game_only", True))
        self.game_only_checkbox.toggled.connect(self._on_change)
        delay_layout.addWidget(self.game_only_checkbox)

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
        general_group_layout.addLayout(delay_layout)
        
        self.general_group.setLayout(general_group_layout)
        layout.addWidget(self.general_group)


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
        
        history_dur_layout.addSpacing(20)
        
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
        
        history_dur_layout.addWidget(self.poll_label)
        history_dur_layout.addWidget(self.poll_slider)
        history_dur_layout.addWidget(self.poll_val_label)
        
        history_layout.addLayout(history_dur_layout)
        
        self.history_group.setLayout(history_layout)
        layout.addWidget(self.history_group)
        
        # TTS Settings
        import importlib.util
        import shutil
        edge_tts_installed = importlib.util.find_spec("edge_tts") is not None
        mpv_installed = shutil.which("mpv") is not None
        tts_available = edge_tts_installed and mpv_installed
        
        self.tts_group = QGroupBox("Text-to-Speech (TTS)")
        tts_layout = QVBoxLayout()
        
        self.tts_checkbox = QCheckBox("Enable TTS Voice Announcements")
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
        
        # Join & Leave Event TTS
        events_layout = QHBoxLayout()
        
        self.tts_join_checkbox = QCheckBox("Announce Join:")
        self.tts_join_checkbox.setChecked(self.config.get("tts_join_enabled", True))
        self.tts_join_checkbox.toggled.connect(self._on_change)
        events_layout.addWidget(self.tts_join_checkbox)
        
        self.tts_join_text = QLineEdit()
        self.tts_join_text.setMaxLength(40)
        self.tts_join_text.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z %]{0,40}$")))
        self.tts_join_text.setText(self.config.get("tts_join_text", "%NICK joined"))
        self.tts_join_text.textChanged.connect(self._on_change)
        events_layout.addWidget(self.tts_join_text)
        
        events_layout.addSpacing(20)
        
        self.tts_leave_checkbox = QCheckBox("Announce Leave:")
        self.tts_leave_checkbox.setChecked(self.config.get("tts_leave_enabled", False))
        self.tts_leave_checkbox.toggled.connect(self._on_change)
        events_layout.addWidget(self.tts_leave_checkbox)
        
        self.tts_leave_text = QLineEdit()
        self.tts_leave_text.setMaxLength(40)
        self.tts_leave_text.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z %]{0,40}$")))
        self.tts_leave_text.setText(self.config.get("tts_leave_text", "%NICK left"))
        self.tts_leave_text.textChanged.connect(self._on_change)
        events_layout.addWidget(self.tts_leave_text)
        
        tts_layout.addLayout(events_layout)
        
        # Variable Info Label
        var_info_label = QLabel("Use %NICK in the text above to insert the user's name.")
        var_font = var_info_label.font()
        var_font.setPointSize(var_font.pointSize() - 2)
        var_info_label.setFont(var_font)
        var_info_label.setStyleSheet("color: gray;")
        tts_layout.addWidget(var_info_label)
        
        # Enable/disable sub-options based on master checkbox
        def update_tts_children(enabled):
            self.tts_join_checkbox.setEnabled(enabled)
            self.tts_join_text.setEnabled(enabled and self.tts_join_checkbox.isChecked())
            self.tts_leave_checkbox.setEnabled(enabled)
            self.tts_leave_text.setEnabled(enabled and self.tts_leave_checkbox.isChecked())
            
        self.tts_checkbox.toggled.connect(update_tts_children)
        self.tts_join_checkbox.toggled.connect(lambda e: self.tts_join_text.setEnabled(e and self.tts_checkbox.isChecked()))
        self.tts_leave_checkbox.toggled.connect(lambda e: self.tts_leave_text.setEnabled(e and self.tts_checkbox.isChecked()))
        update_tts_children(self.tts_checkbox.isChecked())
        
        tts_sliders_layout = QHBoxLayout()
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
        
        tts_sliders_layout.addWidget(self.tts_delay_label)
        tts_sliders_layout.addWidget(self.tts_delay_slider)
        tts_sliders_layout.addWidget(self.tts_delay_val_label)
        
        # Voice selection
        tts_voice_layout = QHBoxLayout()
        tts_voice_layout.addWidget(QLabel("Voice:"))
        self.tts_voice_combo = QComboBox()
        self.tts_voices = [
            ("English (US, Female) - Aria", "en-US-AriaNeural"),
            ("English (US, Male) - Guy", "en-US-GuyNeural"),
            ("English (UK, Female) - Sonia", "en-GB-SoniaNeural"),
            ("English (UK, Male) - Ryan", "en-GB-RyanNeural"),
            ("Polish (Female) - Zofia", "pl-PL-ZofiaNeural"),
            ("Polish (Male) - Marek", "pl-PL-MarekNeural"),
            ("German (Female) - Katja", "de-DE-KatjaNeural"),
            ("German (Male) - Conrad", "de-DE-ConradNeural"),
            ("French (Female) - Denise", "fr-FR-DeniseNeural"),
            ("French (Male) - Henri", "fr-FR-HenriNeural")
        ]
        for label, val in self.tts_voices:
            self.tts_voice_combo.addItem(label, val)
        
        current_voice = self.config.get("tts_voice", "en-US-AriaNeural")
        if current_voice == "pl-PL-AgnieszkaNeural":
            current_voice = "pl-PL-ZofiaNeural"
            self.config["tts_voice"] = current_voice
        idx = self.tts_voice_combo.findData(current_voice)
        if idx >= 0:
            self.tts_voice_combo.setCurrentIndex(idx)
            
        self.tts_voice_combo.currentIndexChanged.connect(self._on_change)
        self.tts_voice_combo.setEnabled(self.tts_checkbox.isChecked())
        self.tts_checkbox.toggled.connect(self.tts_voice_combo.setEnabled)
        
        tts_voice_layout.addWidget(self.tts_voice_combo)
        
        tts_voice_layout.addWidget(QLabel("Speed:"))
        self.tts_rate_combo = QComboBox()
        self.tts_rates = [
            ("Slow (-25%)", "-25%"),
            ("Normal", "+0%"),
            ("Fast (+25%)", "+25%"),
            ("Very Fast (+50%)", "+50%")
        ]
        for label, val in self.tts_rates:
            self.tts_rate_combo.addItem(label, val)
            
        current_rate = self.config.get("tts_rate", "+0%")
        idx = self.tts_rate_combo.findData(current_rate)
        if idx >= 0:
            self.tts_rate_combo.setCurrentIndex(idx)
            
        self.tts_rate_combo.currentIndexChanged.connect(self._on_change)
        self.tts_rate_combo.setEnabled(self.tts_checkbox.isChecked())
        self.tts_checkbox.toggled.connect(self.tts_rate_combo.setEnabled)
        
        tts_voice_layout.addWidget(self.tts_rate_combo)
        
        self.tts_test_nick = QLineEdit("Arkanis")
        self.tts_test_nick.setFixedWidth(80)
        self.tts_test_nick.setToolTip("Nick do testowania wymowy")
        self.tts_test_nick.setEnabled(self.tts_checkbox.isChecked())
        self.tts_checkbox.toggled.connect(self.tts_test_nick.setEnabled)
        tts_voice_layout.addWidget(self.tts_test_nick)
        
        self.tts_test_btn = QPushButton("Test")
        self.tts_test_btn.setFixedWidth(60)
        self.tts_test_btn.clicked.connect(self._test_voice)
        self.tts_test_btn.setEnabled(self.tts_checkbox.isChecked())
        self.tts_checkbox.toggled.connect(self.tts_test_btn.setEnabled)
        tts_voice_layout.addWidget(self.tts_test_btn)
        tts_voice_layout.addStretch()
        
        self.tts_alias_btn = QPushButton("Lista Zastąpień")
        self.tts_alias_btn.clicked.connect(self._open_alias_window)
        tts_voice_layout.addWidget(self.tts_alias_btn)
        
        tts_layout.addLayout(tts_voice_layout)
        
        self.tts_vol_label = QLabel("Volume:")
        self.tts_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_vol_slider.setMinimum(0)
        self.tts_vol_slider.setMaximum(100)
        self.tts_vol_slider.setSingleStep(5)
        self.tts_vol_slider.setTickInterval(10)
        self.tts_vol_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        current_tts_vol = self.config.get("tts_volume", 80)
        self.tts_vol_val_label = QLabel(f"{current_tts_vol}%")
        self.tts_vol_val_label.setMinimumWidth(60)
        self.tts_vol_slider.blockSignals(True)
        self.tts_vol_slider.setValue(current_tts_vol)
        self.tts_vol_slider.blockSignals(False)
        self.tts_vol_slider.valueChanged.connect(lambda v: self.tts_vol_val_label.setText(f"{v}%"))
        self.tts_vol_slider.valueChanged.connect(self._on_change)
        
        self.tts_vol_slider.setEnabled(self.tts_checkbox.isChecked())
        self.tts_checkbox.toggled.connect(self.tts_vol_slider.setEnabled)
        
        tts_sliders_layout.addWidget(self.tts_vol_label)
        tts_sliders_layout.addWidget(self.tts_vol_slider)
        tts_sliders_layout.addWidget(self.tts_vol_val_label)
        tts_layout.addLayout(tts_sliders_layout)
        
        # Cache controls
        tts_cache_layout = QHBoxLayout()
        from tts_manager import get_tts_manager
        tts_manager = get_tts_manager()
        size_mb = tts_manager.get_cache_size()
        
        self.cache_size_label = QLabel(f"Cache size: {size_mb:.2f} MB")
        self.cache_size_label.setFixedWidth(140)
        tts_cache_layout.addWidget(self.cache_size_label)
        
        self.cache_retention_checkbox = QCheckBox("Auto-clear older than:")
        retention_days = self.config.get("tts_cache_retention_days", 30)
        self.cache_retention_checkbox.setChecked(retention_days > 0)
        self.cache_retention_checkbox.toggled.connect(self._on_change)
        tts_cache_layout.addWidget(self.cache_retention_checkbox)
        
        self.cache_retention_spin = QSpinBox()
        self.cache_retention_spin.setRange(1, 365)
        self.cache_retention_spin.setValue(retention_days if retention_days > 0 else 30)
        self.cache_retention_spin.setSuffix(" days")
        self.cache_retention_spin.setEnabled(self.cache_retention_checkbox.isChecked())
        self.cache_retention_spin.valueChanged.connect(self._on_change)
        self.cache_retention_checkbox.toggled.connect(self.cache_retention_spin.setEnabled)
        tts_cache_layout.addWidget(self.cache_retention_spin)
        
        tts_cache_layout.addStretch()
        
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.clicked.connect(self._clear_tts_cache)
        tts_cache_layout.addWidget(self.clear_cache_btn)
        
        self.open_cache_btn = QPushButton("Open Folder")
        self.open_cache_btn.clicked.connect(self._open_cache_folder)
        tts_cache_layout.addWidget(self.open_cache_btn)
        
        tts_layout.addLayout(tts_cache_layout)
        
        # Path label
        import os
        cache_path = os.path.expanduser("~/.cache/ts3-overlay/tts_cache")
        path_label = QLabel(f"<span style='color: gray; font-size: 10px;'>Path: {cache_path}</span>")
        tts_layout.addWidget(path_label)
        
        self.tts_group.setLayout(tts_layout)
        layout.addWidget(self.tts_group)
        
        # Overlays
        self.monitors_group = QGroupBox("Overlays")
        monitors_group_layout = QVBoxLayout()
        
        monitors_layout = QHBoxLayout()
        self.monitor_checkboxes = {}
        for index in range(1, 5):
            overlay_id = str(index)
            mon_cfg = self.config.get("overlay_ids", {}).get(overlay_id, {})
            
            cb = QCheckBox(f"Enable Overlay {overlay_id}")
            cb.setChecked(mon_cfg.get("enabled", False))
            cb.toggled.connect(self._on_change)
            self.monitor_checkboxes[overlay_id] = cb
            monitors_layout.addWidget(cb)
            
        monitors_group_layout.addLayout(monitors_layout)

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
        monitors_group_layout.addLayout(width_layout)

        # Opacity Sliders (Combined)
        opacity_layout = QHBoxLayout()
        self.opacity_normal_label = QLabel("Background Opacity (Normal Mode):")
        self.opacity_normal_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_normal_slider.setRange(0, 100)
        self.opacity_normal_slider.setValue(int(self.config.get("opacity_normal", 0.0) * 100))
        self.opacity_normal_slider.valueChanged.connect(self._update_opacity_normal_label)
        self.opacity_normal_slider.valueChanged.connect(self._on_change)
        self.opacity_normal_val_label = QLabel(f"{self.opacity_normal_slider.value()}%")
        
        self.opacity_move_label = QLabel("Opacity (Move Mode):")
        self.opacity_move_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_move_slider.setRange(0, 100)
        self.opacity_move_slider.setValue(int(self.config.get("opacity_move", self.config.get("opacity", 0.8)) * 100))
        self.opacity_move_slider.valueChanged.connect(self._update_opacity_move_label)
        self.opacity_move_slider.valueChanged.connect(self._on_change)
        self.opacity_move_val_label = QLabel(f"{self.opacity_move_slider.value()}%")
        
        opacity_layout.addWidget(self.opacity_normal_label)
        opacity_layout.addWidget(self.opacity_normal_slider)
        opacity_layout.addWidget(self.opacity_normal_val_label)
        opacity_layout.addSpacing(20)
        opacity_layout.addWidget(self.opacity_move_label)
        opacity_layout.addWidget(self.opacity_move_slider)
        opacity_layout.addWidget(self.opacity_move_val_label)
        monitors_group_layout.addLayout(opacity_layout)

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
        font_layout.addStretch()
        monitors_group_layout.addLayout(font_layout)

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
        
        monitors_group_layout.addLayout(color_layout)

        # Misc Settings
        misc_layout = QHBoxLayout()
        self.header_checkbox = QCheckBox("Show Title Header (Logo + Text)")
        self.header_checkbox.setChecked(self.config.get("show_header", True))
        self.header_checkbox.toggled.connect(self._on_change)
        misc_layout.addWidget(self.header_checkbox)
        
        self.three_dots_checkbox = QCheckBox("Show Dots Indicator (number of dots indicates ID number of overlay)")
        self.three_dots_checkbox.setChecked(self.config.get("show_three_dots", False))
        self.three_dots_checkbox.toggled.connect(self._on_change)
        misc_layout.addWidget(self.three_dots_checkbox)
        
        self.disable_blink_checkbox = QCheckBox("Disable border blinking on startup")
        self.disable_blink_checkbox.setChecked(self.config.get("disable_blink", False))
        self.disable_blink_checkbox.toggled.connect(self._on_change)
        misc_layout.addWidget(self.disable_blink_checkbox)
        
        monitors_group_layout.addLayout(misc_layout)
        
        self.monitors_group.setLayout(monitors_group_layout)
        layout.addWidget(self.monitors_group)
        
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Close")
        self.save_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.save_btn)
        
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.scroll_area.setWidget(self.container_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        self.resize(1000, min(self.container_widget.sizeHint().height() + 20, 768))
        
        # Prevent accidental scrolling changes
        self.scroll_filter = ScrollFilter(self)
        for child in self.container_widget.findChildren(QWidget):
            if isinstance(child, (QSlider, QSpinBox, QComboBox)):
                child.installEventFilter(self.scroll_filter)
                # Only allow wheel scroll when the user specifically clicks and focuses on the widget
                child.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        
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
        if hasattr(self, 'tts_join_checkbox'):
            self.config["tts_join_enabled"] = self.tts_join_checkbox.isChecked()
            self.config["tts_join_text"] = self.tts_join_text.text()
            self.config["tts_leave_enabled"] = self.tts_leave_checkbox.isChecked()
            self.config["tts_leave_text"] = self.tts_leave_text.text()
        self.config["tts_voice"] = self.tts_voice_combo.currentData()
        self.config["tts_rate"] = self.tts_rate_combo.currentData()
        self.config["tts_delay_ms"] = self.tts_delay_slider.value()
        self.config["tts_volume"] = self.tts_vol_slider.value()
        
        if self.cache_retention_checkbox.isChecked():
            self.config["tts_cache_retention_days"] = self.cache_retention_spin.value()
        else:
            self.config["tts_cache_retention_days"] = 0
            
        self.config["history_duration"] = self.history_dur_slider.value()
        
        # Emit signal to inform main app to apply changes
        self.config_changed.emit()
        
    def _open_alias_window(self):
        from alias_window import AliasWindow
        dlg = AliasWindow(self.config.get("tts_aliases", {}), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.config["tts_aliases"] = dlg.get_aliases()
            self._on_change()
        dlg.deleteLater()

    def _test_voice(self):
        import subprocess
        import shutil
        import tempfile
        import os
        import threading
        import hashlib
        import sys
        
        voice = self.tts_voice_combo.currentData()
        vol = self.tts_vol_slider.value()
        join_txt = getattr(self, "tts_join_text", None)
        leave_txt = getattr(self, "tts_leave_text", None)
        j_t = join_txt.text() if join_txt else "%NICK joined"
        l_t = leave_txt.text() if leave_txt else "%NICK left"
        
        test_name = self.tts_test_nick.text() or "Arkanis"
        from tts_manager import get_tts_manager, apply_tts_aliases
        aliases = self.config.get("tts_aliases", {})
        spoken_name = apply_tts_aliases(test_name, aliases)
        
        custom_text = f"{j_t.replace('%NICK', spoken_name)}. {l_t.replace('%NICK', spoken_name)}."
        
        delay = self.config.get("tts_delay_ms", 0) / 1000.0
        get_tts_manager(self.config).enqueue(
            text=custom_text,
            voice=self.tts_voice_combo.currentData(),
            volume=self.tts_vol_slider.value(),
            delay=0, # No delay for test button
            rate=self.tts_rate_combo.currentData()
        )
        
        # Update cache size label after test (give worker time to download)
        from PyQt6.QtCore import QTimer
        def update_cache():
            size_mb = get_tts_manager().get_cache_size()
            self.cache_size_label.setText(f"Cache size: {size_mb:.2f} MB")
        QTimer.singleShot(2000, update_cache)

    def _open_cache_folder(self):
        import os
        cache_path = os.path.expanduser("~/.cache/ts3-overlay/tts_cache")
        os.makedirs(cache_path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(cache_path))

    def _clear_tts_cache(self):
        reply = QMessageBox.question(
            self, "Clear Cache", 
            "Are you sure you want to delete all cached TTS audio files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from tts_manager import get_tts_manager
            mgr = get_tts_manager()
            if mgr.clear_cache():
                self.cache_size_label.setText("Cache size: 0.00 MB")
                QMessageBox.information(self, "Success", "Cache cleared successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to clear cache.")
