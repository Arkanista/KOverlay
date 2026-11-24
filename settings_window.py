from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QSlider, QCheckBox, QFontComboBox, QSpinBox, QAbstractSpinBox, QColorDialog, QGroupBox,
    QComboBox, QScrollArea, QWidget, QMessageBox, QRadioButton, QApplication, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QEvent, QRegularExpression, QUrl
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QRegularExpressionValidator, QDesktopServices, QIntValidator, QPalette, QIcon
import os
import sys
import shutil
import importlib.util
import subprocess
import tempfile
import threading
import hashlib
from tts_manager import get_tts_manager

class LineHeightSpinBox(QSpinBox):
    def __init__(self, get_auto_val, parent=None):
        super().__init__(parent)
        self.get_auto_val = get_auto_val

    def stepEnabled(self):
        flags = QAbstractSpinBox.StepEnabledFlag.StepNone
        if not self.isReadOnly():
            if self.value() < self.maximum():
                flags |= QAbstractSpinBox.StepEnabledFlag.StepUpEnabled
            if self.value() > 0 or self.get_auto_val() > 1:
                flags |= QAbstractSpinBox.StepEnabledFlag.StepDownEnabled
        return flags

    def stepBy(self, steps):
        auto_h = self.get_auto_val()
        if self.value() == 0:
            if steps > 0:
                self.setValue(auto_h + (steps - 1) if auto_h > 0 else steps)
            else:
                self.setValue(max(1, auto_h + steps))
        else:
            new_val = self.value() + steps
            if new_val < 0:
                new_val = 0
            self.setValue(new_val)

class ScrollFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if not obj.hasFocus():
                event.ignore()
                return True
        return super().eventFilter(obj, event)

class SettingsWindow(QWidget):
    config_changed = pyqtSignal()
    finished = pyqtSignal(int)
    closed = pyqtSignal()
    reset_positions_requested = pyqtSignal()

    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KOverlay Settings")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(960)
        self.resize(1100, 768)
        self.setMinimumHeight(400)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
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
        self._is_closing = False
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.container_widget = QWidget()
        layout = QVBoxLayout(self.container_widget)

        # Prominent Info Banner
        self.banner_label = QLabel("ℹ️ <b>Important:</b> KOverlay must remain running in the background (system tray) for the overlay to appear.")
        self.banner_label.setWordWrap(True)
        layout.addWidget(self.banner_label)
        self._update_banner_style()
        
        # General Settings Group
        from i18n import tr, get_available_languages, set_language, USER_LOCALES_DIR
        self.general_group = QGroupBox(tr("settings.group_general", "Voice Backend & Connection"))
        general_group_layout = QVBoxLayout()

        # Language Selector
        lang_layout = QHBoxLayout()
        self.language_label = QLabel(f"<b>{tr('settings.language', 'Language:')}</b>")
        lang_layout.addWidget(self.language_label)
        self.language_combo = QComboBox()
        for code, disp_name in get_available_languages().items():
            self.language_combo.addItem(f"{disp_name} ({code})", code)
        cur_lang = self.config.get("language", "en")
        lang_idx = self.language_combo.findData(cur_lang)
        if lang_idx >= 0:
            self.language_combo.setCurrentIndex(lang_idx)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self.language_combo)

        self.open_locales_btn = QPushButton(tr("settings.open_locales_btn", "Open Locales Folder"))
        self.open_locales_btn.setToolTip(f"User-editable translations folder: {USER_LOCALES_DIR}")
        self.open_locales_btn.clicked.connect(self._open_locales_folder)
        lang_layout.addWidget(self.open_locales_btn)
        lang_layout.addStretch()
        general_group_layout.addLayout(lang_layout)
        
        # Voice Platform Selection
        backend_layout = QHBoxLayout()
        self.voice_platform_label = QLabel("<b>Voice Platform:</b>")
        backend_layout.addWidget(self.voice_platform_label)
        self.backend_ts3_radio = QRadioButton("TeamSpeak 3")
        self.backend_mumble_radio = QRadioButton("Mumble")
        self.backend_discord_radio = QRadioButton("Discord")

        current_backend = self.config.get("voice_backend", "ts3")
        if current_backend == "discord":
            self.backend_discord_radio.setChecked(True)
        elif current_backend == "mumble":
            self.backend_mumble_radio.setChecked(True)
        else:
            self.backend_ts3_radio.setChecked(True)

        self.backend_ts3_radio.toggled.connect(self._on_backend_toggled)
        self.backend_mumble_radio.toggled.connect(self._on_backend_toggled)
        self.backend_discord_radio.toggled.connect(self._on_backend_toggled)

        backend_layout.addWidget(self.backend_ts3_radio)
        backend_layout.addWidget(self.backend_mumble_radio)
        backend_layout.addWidget(self.backend_discord_radio)
        backend_layout.addStretch()
        general_group_layout.addLayout(backend_layout)

        # Platform specific widgets
        # 1. TS3 Widget
        self.ts3_widget = QWidget()
        ts3_layout = QHBoxLayout(self.ts3_widget)
        ts3_layout.setContentsMargins(0, 0, 0, 0)
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_key_input.setPlaceholderText("Enter TS3 API Key here")
        self.api_key_input.editingFinished.connect(self._on_change)
        self.ts3_key_label = QLabel("TS3 API Key:")
        ts3_layout.addWidget(self.ts3_key_label)
        ts3_layout.addWidget(self.api_key_input)
        general_group_layout.addWidget(self.ts3_widget)

        # 2. Mumble Widget
        self.mumble_widget = QWidget()
        mumble_layout = QHBoxLayout(self.mumble_widget)
        mumble_layout.setContentsMargins(0, 0, 0, 0)
        self.mumble_port_label = QLabel("Mumble IPC Port:")
        mumble_layout.addWidget(self.mumble_port_label)
        self.mumble_port_spin = QSpinBox()
        self.mumble_port_spin.setRange(1024, 65535)
        self.mumble_port_spin.setValue(self.config.get("mumble_port", 25640))
        self.mumble_port_spin.valueChanged.connect(self._on_change)
        mumble_layout.addWidget(self.mumble_port_spin)

        self.mumble_install_btn = QPushButton("Install / Recompile Mumble Plugin")
        self.mumble_install_btn.clicked.connect(self._install_mumble_plugin)
        mumble_layout.addWidget(self.mumble_install_btn)
        mumble_layout.addStretch()
        general_group_layout.addWidget(self.mumble_widget)

        # 3. Discord Widget (2 rows so translations never overflow horizontally)
        self.discord_widget = QWidget()
        discord_layout = QVBoxLayout(self.discord_widget)
        discord_layout.setContentsMargins(0, 0, 0, 0)
        discord_layout.setSpacing(6)

        discord_row1 = QHBoxLayout()
        self.discord_status_label = QLabel("Discord connects automatically via local IPC.")
        discord_row1.addWidget(self.discord_status_label)
        self.discord_auth_btn = QPushButton("Authorize Discord")
        self.discord_auth_btn.clicked.connect(self._on_discord_auth_btn_clicked)
        discord_row1.addWidget(self.discord_auth_btn)

        self.discord_reauth_btn = QPushButton("Re-authorize")
        self.discord_reauth_btn.setToolTip("Request a fresh Discord authorization token without unauthorizing first.")
        self.discord_reauth_btn.clicked.connect(self._start_discord_authorization)
        discord_row1.addWidget(self.discord_reauth_btn)
        discord_row1.addStretch()
        discord_layout.addLayout(discord_row1)

        discord_row2 = QHBoxLayout()
        self.discord_icons_checkbox = QCheckBox("Show status icons (mute, deafen, etc.)")
        self.discord_icons_checkbox.setChecked(self.config.get("discord_show_status_icons", True))
        self.discord_icons_checkbox.toggled.connect(self._on_change)
        discord_row2.addWidget(self.discord_icons_checkbox)

        discord_row2.addSpacing(10)
        self.discord_icons_side_label = QLabel("Icons side:")
        discord_row2.addWidget(self.discord_icons_side_label)
        self.discord_icons_pos_combo = QComboBox()
        self.discord_icons_pos_combo.addItem("Right of nickname (Default)", "right")
        self.discord_icons_pos_combo.addItem("Left of nickname", "left")
        cur_icon_pos = self.config.get("discord_status_icons_position", "right")
        idx_icon_pos = self.discord_icons_pos_combo.findData(cur_icon_pos)
        self.discord_icons_pos_combo.setCurrentIndex(idx_icon_pos if idx_icon_pos >= 0 else 0)
        self.discord_icons_pos_combo.setEnabled(self.discord_icons_checkbox.isChecked())
        self.discord_icons_checkbox.toggled.connect(self.discord_icons_pos_combo.setEnabled)
        self.discord_icons_pos_combo.currentIndexChanged.connect(self._on_change)
        discord_row2.addWidget(self.discord_icons_pos_combo)
        discord_row2.addStretch()
        discord_layout.addLayout(discord_row2)

        general_group_layout.addWidget(self.discord_widget)
        self._auth_thread = None

        # Sync initial visibility
        self._sync_backend_widgets()

        # Target Window Keywords
        keywords_layout = QHBoxLayout()
        self.keywords_input = QLineEdit()
        current_keywords = self.config.get("target_keywords", ["EVE - ", "exefile.exe"])
        self.keywords_input.setText(", ".join(current_keywords))
        self.keywords_input.setPlaceholderText("e.g. EVE - , exefile.exe")
        self.keywords_input.editingFinished.connect(self._on_change)
        self.keywords_label = QLabel("Target Window Keywords (comma separated):")
        keywords_layout.addWidget(self.keywords_label)
        keywords_layout.addWidget(self.keywords_input)
        general_group_layout.addLayout(keywords_layout)
        
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
        
        self.history_checkbox = QCheckBox("Enable Join/Leave History (🡅 / 🡇 indicators)")
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
        
        self.history_dur_label = QLabel("Duration:")
        history_dur_layout.addWidget(self.history_dur_label)
        history_dur_layout.addWidget(self.history_dur_slider)
        history_dur_layout.addWidget(self.history_dur_val_label)
        
        history_dur_layout.addSpacing(20)
        
        # History settings are self-contained now
        
        history_layout.addLayout(history_dur_layout)
        
        self.history_group.setLayout(history_layout)
        layout.addWidget(self.history_group)

        # Speakers and User List Behavior
        self.speakers_group = QGroupBox("User List & Speaking Behavior")
        speakers_layout = QVBoxLayout()

        # Row 1: Sorting options & Limit users
        row1_layout = QHBoxLayout()
        self.sorting_label = QLabel("User list sorting:")
        row1_layout.addWidget(self.sorting_label)
        
        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItem("Alphabetical (recent speakers on top while fading)", "alphabetical_fading_top")
        self.sort_order_combo.addItem("Recent speakers on top (most recent first)", "recent_speakers")
        self.sort_order_combo.addItem("Alphabetical (speakers in-place)", "alphabetical")
        
        current_sort = self.config.get("sort_order")
        if not current_sort:
            if "recent_speakers_first" in self.config and self.config.get("recent_speakers_first", False):
                current_sort = "recent_speakers"
            else:
                current_sort = "alphabetical_fading_top"
                
        idx = self.sort_order_combo.findData(current_sort)
        if idx >= 0:
            self.sort_order_combo.setCurrentIndex(idx)
        else:
            self.sort_order_combo.setCurrentIndex(0)
            
        self.sort_order_combo.currentIndexChanged.connect(self._on_change)
        row1_layout.addWidget(self.sort_order_combo)
        row1_layout.addSpacing(25)

        self.limit_users_checkbox = QCheckBox("Limit user list to:")
        self.limit_users_checkbox.setChecked(self.config.get("limit_users_enabled", False))
        self.limit_users_checkbox.toggled.connect(self._on_change)
        row1_layout.addWidget(self.limit_users_checkbox)

        self.limit_users_input = QLineEdit()
        self.limit_users_input.setValidator(QIntValidator(1, 9999))
        self.limit_users_input.setText(str(self.config.get("limit_users_count", "10")))
        self.limit_users_input.setFixedWidth(50)
        self.limit_users_input.setEnabled(self.limit_users_checkbox.isChecked())
        self.limit_users_checkbox.toggled.connect(self.limit_users_input.setEnabled)
        self.limit_users_input.textChanged.connect(self._on_change)
        row1_layout.addWidget(self.limit_users_input)
        self.users_suffix_label = QLabel("users")
        row1_layout.addWidget(self.users_suffix_label)
        row1_layout.addStretch()
        speakers_layout.addLayout(row1_layout)

        # Informational note regarding users who left
        self.sort_note_label = QLabel("<span style='color: gray; font-size: 11px;'>Note: Users who left the channel are always placed at the bottom of the list.</span>")
        speakers_layout.addWidget(self.sort_note_label)

        # Row 2: Speaker fade duration (0-60s)
        fade_layout = QHBoxLayout()
        self.fade_label = QLabel("Keep recent speakers highlighted (fade duration):")
        fade_layout.addWidget(self.fade_label)
        self.speaker_fade_slider = QSlider(Qt.Orientation.Horizontal)
        self.speaker_fade_slider.setRange(0, 60)
        self.speaker_fade_slider.setValue(int(self.config.get("speaker_fade_duration", 5)))
        fade_val = self.speaker_fade_slider.value()
        self.speaker_fade_val_label = QLabel(f"{fade_val}s" if fade_val > 0 else "0s (Off)")
        self.speaker_fade_val_label.setMinimumWidth(60)

        def on_fade_slider_changed(val):
            self.speaker_fade_val_label.setText(f"{val}s" if val > 0 else "0s (Off)")
            self._on_change()

        self.speaker_fade_slider.valueChanged.connect(on_fade_slider_changed)
        fade_layout.addWidget(self.speaker_fade_slider)
        fade_layout.addWidget(self.speaker_fade_val_label)
        speakers_layout.addLayout(fade_layout)

        # Row 3: Nickname cleaning (brackets & prefix list)
        nick_layout = QHBoxLayout()
        self.strip_brackets_checkbox = QCheckBox("Remove all bracket tags ([...], (...), {...})")
        self.strip_brackets_checkbox.setChecked(self.config.get("strip_bracket_tags", False))
        self.strip_brackets_checkbox.toggled.connect(self._on_change)
        nick_layout.addWidget(self.strip_brackets_checkbox)
        nick_layout.addSpacing(20)

        self.nick_prefix_btn = QPushButton("Nick Prefixes...")
        self.nick_prefix_btn.clicked.connect(self._open_prefix_window)
        nick_layout.addWidget(self.nick_prefix_btn)
        
        prefix_count = len(self.config.get("nickname_prefixes", []))
        self.prefix_count_label = QLabel(f"({prefix_count} custom)" if prefix_count > 0 else "")
        nick_layout.addWidget(self.prefix_count_label)
        nick_layout.addStretch()
        speakers_layout.addLayout(nick_layout)

        self.speakers_group.setLayout(speakers_layout)
        layout.addWidget(self.speakers_group)
        
        # TTS Settings
        from tts_manager import check_tts_status, get_tts_manager
        preferred_player = self.config.get("tts_audio_player", "auto")
        tts_status = check_tts_status(preferred_player)
        
        self.tts_group = QGroupBox("Text-to-Speech (TTS)")
        tts_layout = QVBoxLayout()
        
        tts_header_layout = QHBoxLayout()
        self.tts_checkbox = QCheckBox("Enable TTS Voice Announcements")
        self.tts_checkbox.setChecked(self.config.get("tts_enabled", False))
        
        self.tts_status_label = QLabel()
        self.install_tts_btn = QPushButton("Install edge-tts")
        self.install_tts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_tts_btn.setVisible(False)

        player_descriptions = {
            "mpv": "mpv ★ Recommended (gapless silence removal)",
            "ffplay": "ffplay ★ Recommended (gapless silence removal)",
            "pw-play": "pw-play ● Standard (PipeWire native, no silence trim)",
            "paplay": "paplay ○ Fallback (PulseAudio, no silence trim)",
            "gst-play-1.0": "gst-play-1.0 ○ Fallback (GStreamer, higher latency)",
            "cvlc": "cvlc ○ Fallback (VLC CLI, higher overhead)",
            "win32_mci": "Windows MCI (built-in)",
        }

        player_short_names = {
            "mpv": "mpv (gapless silence removal)",
            "ffplay": "ffplay / FFmpeg (gapless silence removal)",
            "pw-play": "pw-play (PipeWire native)",
            "paplay": "paplay (PulseAudio / PipeWire-Pulse)",
            "gst-play-1.0": "gst-play-1.0 (GStreamer)",
            "cvlc": "cvlc (VLC CLI)",
            "win32_mci": "Windows MCI (built-in)",
        }

        def update_tts_status_ui(status, auto_enable_on_ready=False):
            available = status["available"]
            p_type = status.get("player_type")
            p_bin = status.get("player_bin") or ""
            p_desc = player_short_names.get(p_type, p_type or "none")

            if available:
                from i18n import tr
                self.install_tts_btn.setVisible(False)
                self.tts_checkbox.setText(tr("settings.tts_enable", "Enable TTS Voice Announcements"))
                self.tts_checkbox.setEnabled(True)
                if auto_enable_on_ready:
                    self.tts_checkbox.setChecked(True)
                is_recommended = p_type in ("mpv", "ffplay", "win32_mci")
                badge_color = "#4caf50" if is_recommended else "#ffb74d"
                rec_note = " ★ Recommended" if p_type in ("mpv", "ffplay") else (" (Fallback)" if sys.platform != "win32" else "")
                self.tts_status_label.setText(f"✓ Ready — Active engine: <b>{p_desc}</b>{rec_note}")
                self.tts_status_label.setStyleSheet(f"color: {badge_color}; font-size: 11px;")
                if p_bin and p_bin != "win32_mci":
                    self.tts_status_label.setToolTip(f"Executable: {p_bin}")
                else:
                    self.tts_status_label.setToolTip("")
            else:
                self.tts_checkbox.setChecked(False)
                self.tts_checkbox.setEnabled(False)
                self.config["tts_enabled"] = False
                missing_parts = []
                if not status["edge_tts"]:
                    missing_parts.append("edge-tts module")
                    self.install_tts_btn.setVisible(True)
                else:
                    self.install_tts_btn.setVisible(False)
                if not p_type:
                    missing_parts.append("audio player")
                reason = f": missing {', '.join(missing_parts)}" if missing_parts else ""
                self.tts_checkbox.setText(f"Enable TTS Announcements (Unavailable{reason})")

                if not status["edge_tts"] and p_type:
                    self.tts_status_label.setText(
                        f"⚠ Cause: missing <b>edge-tts</b> Python module (Audio player ready: <b>{p_desc}</b>)"
                    )
                elif status["edge_tts"] and not p_type:
                    self.tts_status_label.setText(
                        "⚠ Cause: no supported audio player found (install <b>mpv</b>, <b>pw-play</b>, <b>paplay</b>, or <b>ffplay</b>)"
                    )
                else:
                    self.tts_status_label.setText(
                        "⚠ Cause: missing <b>edge-tts</b> module and audio player (<b>mpv</b> / <b>pw-play</b> / <b>paplay</b>)"
                    )
                self.tts_status_label.setStyleSheet("color: #e57373; font-size: 11px;")
                self.tts_status_label.setToolTip("")

        update_tts_status_ui(tts_status)

        def on_install_edge_tts():
            self.install_tts_btn.setEnabled(False)
            self.install_tts_btn.setText("Installing...")
            QApplication.processEvents()
            success = False
            commands = [
                [sys.executable, "-m", "pip", "install", "edge-tts"],
                [sys.executable, "-m", "pip", "install", "--user", "edge-tts"],
                [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "edge-tts"],
            ]
            for cmd in commands:
                try:
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                    if res.returncode == 0:
                        success = True
                        break
                except Exception:
                    pass
            if not success and sys.platform != "win32":
                try:
                    venv_dir = os.path.expanduser("~/.local/share/koverlay/venv")
                    if not os.path.exists(os.path.join(venv_dir, "bin", "pip")):
                        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True, timeout=30)
                    res = subprocess.run([os.path.join(venv_dir, "bin", "pip"), "install", "edge-tts"], timeout=60)
                    if res.returncode == 0:
                        success = True
                except Exception:
                    pass
            cur_pref = self.tts_player_combo.currentData() if hasattr(self, "tts_player_combo") else self.config.get("tts_audio_player", "auto")
            new_status = get_tts_manager(self.config).refresh_capabilities(cur_pref)
            update_tts_status_ui(new_status, auto_enable_on_ready=True)
            if not new_status["available"]:
                self.install_tts_btn.setEnabled(True)
                self.install_tts_btn.setText("Retry Install edge-tts")

        self.install_tts_btn.clicked.connect(on_install_edge_tts)
        self.tts_checkbox.toggled.connect(self._on_change)
        tts_header_layout.addWidget(self.tts_checkbox)
        tts_header_layout.addWidget(self.install_tts_btn)
        tts_header_layout.addSpacing(10)
        tts_header_layout.addWidget(self.tts_status_label)
        tts_header_layout.addStretch()
        tts_layout.addLayout(tts_header_layout)

        # Linux-only Audio Engine Switcher & Recommendations Info Popup
        if sys.platform != "win32":
            available_players = tts_status.get("available_players", [])
            player_row_layout = QHBoxLayout()
            self.tts_engine_label = QLabel("Audio Engine (Linux):")
            player_row_layout.addWidget(self.tts_engine_label)

            self.tts_player_combo = QComboBox()
            best_auto = available_players[0][0] if available_players else "none"
            self.tts_player_combo.addItem(f"Auto (Best detected: {best_auto})", "auto")
            for p_type, p_bin in available_players:
                label = player_descriptions.get(p_type, p_type)
                self.tts_player_combo.addItem(f"{label}  [{p_bin}]", p_type)

            idx_p = self.tts_player_combo.findData(preferred_player)
            if idx_p >= 0:
                self.tts_player_combo.setCurrentIndex(idx_p)
            else:
                self.tts_player_combo.setCurrentIndex(0)

            # Enable switcher when more than 1 engine is available (or if user had a non-auto selection)
            self.tts_player_combo.setEnabled(len(available_players) > 1)
            if len(available_players) <= 1:
                self.tts_player_combo.setToolTip("Only one audio player was detected on this system.")
            else:
                self.tts_player_combo.setToolTip("Select which detected Linux audio player KOverlay should use for TTS playback.")

            def on_player_combo_changed():
                chosen = self.tts_player_combo.currentData()
                self.config["tts_audio_player"] = chosen
                new_st = get_tts_manager(self.config).refresh_capabilities(chosen)
                update_tts_status_ui(new_st)
                self._on_change()

            self.tts_player_combo.currentIndexChanged.connect(on_player_combo_changed)
            player_row_layout.addWidget(self.tts_player_combo)

            self.tts_player_info_btn = QPushButton("Which engine is best?")
            info_icon = QIcon.fromTheme(
                "dialog-information",
                self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
            )
            if not info_icon.isNull():
                self.tts_player_info_btn.setIcon(info_icon)
            self.tts_player_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def show_player_recommendations():
                from i18n import tr
                cur_st = check_tts_status(self.tts_player_combo.currentData())
                det_list = cur_st.get("available_players", [])
                active_p = cur_st.get("player_type")
                active_badge = tr("settings.engine_dlg_active", "[ACTIVE]")
                if det_list:
                    detected_html = "".join(
                        f"&bull; <b>{pt}</b> (<code>{pb}</code>)"
                        + (f" &mdash; <span style='color:#4caf50;'><b>{active_badge}</b></span>" if pt == active_p else "")
                        + "<br>"
                        for pt, pb in det_list
                    )
                else:
                    detected_html = tr("settings.engine_dlg_none", "<i>No supported audio players detected!</i><br>")

                msg = (
                    tr("settings.engine_dlg_header", "<h3>Linux TTS Audio Engines — Comparison & Recommendations</h3><b>Currently Detected on Your System:</b><br>")
                    + f"{detected_html}<br>"
                    + tr("settings.engine_dlg_body", "")
                )
                QMessageBox.information(self, tr("settings.engine_dlg_title", "TTS Audio Engines — Recommendations"), msg)

            self.tts_player_info_btn.clicked.connect(show_player_recommendations)
            player_row_layout.addWidget(self.tts_player_info_btn)
            player_row_layout.addStretch()
            tts_layout.addLayout(player_row_layout)
        
        if sys.platform == "win32":
            note_text = "Note: Uses high-quality voices over the internet. Requires 'edge-tts' Python module (supports built-in Windows audio or mpv.exe)."
        else:
            note_text = "Note: Uses high-quality voices over the internet. Requires 'edge-tts' and an audio player (mpv, ffplay, pw-play, paplay, or gst-play-1.0)."
        self.tts_info_label = QLabel(note_text)
        font = self.tts_info_label.font()
        font.setPointSize(font.pointSize() - 2)
        self.tts_info_label.setFont(font)
        self.tts_info_label.setStyleSheet("color: gray;")
        self.tts_info_label.setWordWrap(True)
        tts_layout.addWidget(self.tts_info_label)
        
        # Join & Leave Event TTS
        events_layout = QHBoxLayout()
        
        self.tts_join_checkbox = QCheckBox("Announce Join:")
        self.tts_join_checkbox.setChecked(self.config.get("tts_join_enabled", True))
        self.tts_join_checkbox.toggled.connect(self._on_change)
        events_layout.addWidget(self.tts_join_checkbox)
        
        self.tts_join_text = QLineEdit()
        self.tts_join_text.setMaxLength(40)
        self.tts_join_text.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9.,!? %ąćęłńóśźżĄĆĘŁŃÓŚŹŻ-]{0,40}$")))
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
        self.tts_leave_text.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9.,!? %ąćęłńóśźżĄĆĘŁŃÓŚŹŻ-]{0,40}$")))
        self.tts_leave_text.setText(self.config.get("tts_leave_text", "%NICK left"))
        self.tts_leave_text.textChanged.connect(self._on_change)
        events_layout.addWidget(self.tts_leave_text)
        
        tts_layout.addLayout(events_layout)
        
        # Variable Info Label
        self.var_info_label = QLabel("Use %NICK in the text above to insert the user's name.")
        var_font = self.var_info_label.font()
        var_font.setPointSize(var_font.pointSize() - 2)
        self.var_info_label.setFont(var_font)
        self.var_info_label.setStyleSheet("color: gray;")
        tts_layout.addWidget(self.var_info_label)

        # Nickname formatting & Pronunciation layout
        tts_pronunciation_layout = QHBoxLayout()
        
        self.tts_lowercase_checkbox = QCheckBox("Convert to lowercase (better pronunciation of ALL-CAPS)")
        self.tts_lowercase_checkbox.setChecked(self.config.get("tts_lowercase", True))
        self.tts_lowercase_checkbox.setToolTip("Converts uppercase letters to lowercase so TTS reads words smoothly instead of spelling letters out.")
        self.tts_lowercase_checkbox.toggled.connect(self._on_change)
        tts_pronunciation_layout.addWidget(self.tts_lowercase_checkbox)
        
        tts_pronunciation_layout.addSpacing(15)
        
        self.tts_replace_digits_checkbox = QCheckBox("Replace digits with letters (1337)")
        self.tts_replace_digits_checkbox.setChecked(self.config.get("tts_replace_digits", True))
        self.tts_replace_digits_checkbox.setToolTip("Replaces numbers with corresponding letters (e.g. 1->i, 3->e, 4->a) before reading.")
        self.tts_replace_digits_checkbox.toggled.connect(self._on_change)
        tts_pronunciation_layout.addWidget(self.tts_replace_digits_checkbox)
        
        self.tts_digits_btn = QPushButton("Digit Substitutions...")
        self.tts_digits_btn.setToolTip("Configure number-to-letter replacements (0-9)")
        self.tts_digits_btn.clicked.connect(self._open_digits_window)
        self.tts_digits_btn.setEnabled(self.tts_replace_digits_checkbox.isChecked())
        self.tts_replace_digits_checkbox.toggled.connect(self.tts_digits_btn.setEnabled)
        tts_pronunciation_layout.addWidget(self.tts_digits_btn)
        
        tts_pronunciation_layout.addSpacing(10)
        
        self.tts_alias_btn = QPushButton("TTS Aliases...")
        self.tts_alias_btn.setToolTip("Configure custom word/name pronunciation aliases")
        self.tts_alias_btn.clicked.connect(self._open_alias_window)
        tts_pronunciation_layout.addWidget(self.tts_alias_btn)
        
        tts_pronunciation_layout.addStretch()
        tts_layout.addLayout(tts_pronunciation_layout)
        
        # Enable/disable sub-options based on master checkbox
        def update_tts_children(enabled):
            self.tts_join_checkbox.setEnabled(enabled)
            self.tts_join_text.setEnabled(enabled and self.tts_join_checkbox.isChecked())
            self.tts_leave_checkbox.setEnabled(enabled)
            self.tts_leave_text.setEnabled(enabled and self.tts_leave_checkbox.isChecked())
            if hasattr(self, 'tts_lowercase_checkbox'):
                self.tts_lowercase_checkbox.setEnabled(enabled)
            if hasattr(self, 'tts_replace_digits_checkbox'):
                self.tts_replace_digits_checkbox.setEnabled(enabled)
                self.tts_digits_btn.setEnabled(enabled and self.tts_replace_digits_checkbox.isChecked())
            if hasattr(self, 'tts_alias_btn'):
                self.tts_alias_btn.setEnabled(enabled)
            
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
        self.tts_voice_label = QLabel("Voice:")
        tts_voice_layout.addWidget(self.tts_voice_label)
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
        
        self.tts_speed_label = QLabel("Speed:")
        tts_voice_layout.addWidget(self.tts_speed_label)
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
        self.tts_test_nick.setToolTip("Nickname for pronunciation test")
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

        # Ducking controls (lower TTS volume while someone is actively speaking)
        duck_enable_layout = QHBoxLayout()
        self.tts_duck_checkbox = QCheckBox("Duck TTS volume when someone is speaking (real audio)")
        self.tts_duck_checkbox.setChecked(self.config.get("tts_ducking_enabled", True))
        self.tts_duck_checkbox.setToolTip(
            "Lowers TTS volume when a user on the userlist is talking and audio is actually detected from the VoIP app (ignores silent PTT key-up)."
        )
        self.tts_duck_checkbox.toggled.connect(self._on_change)
        duck_enable_layout.addWidget(self.tts_duck_checkbox)
        duck_enable_layout.addStretch()
        tts_layout.addLayout(duck_enable_layout)

        duck_vol_layout = QHBoxLayout()
        self.tts_duck_vol_label = QLabel("Ducking volume:")
        self.tts_duck_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_duck_vol_slider.setMinimum(0)
        self.tts_duck_vol_slider.setMaximum(100)
        self.tts_duck_vol_slider.setSingleStep(5)
        self.tts_duck_vol_slider.setTickInterval(10)
        self.tts_duck_vol_slider.setTickPosition(QSlider.TickPosition.TicksBelow)

        current_duck_pct = self.config.get("tts_duck_volume_pct", 25)
        self.tts_duck_vol_val_label = QLabel()
        self.tts_duck_vol_val_label.setMinimumWidth(95)

        def _update_duck_vol_label(*_):
            pct = self.tts_duck_vol_slider.value()
            eff = int(round(self.tts_vol_slider.value() * (pct / 100.0)))
            self.tts_duck_vol_val_label.setText(f"{pct}% (eff: {eff}%)")

        self.tts_duck_vol_slider.blockSignals(True)
        self.tts_duck_vol_slider.setValue(current_duck_pct)
        self.tts_duck_vol_slider.blockSignals(False)
        _update_duck_vol_label()
        self.tts_duck_vol_slider.valueChanged.connect(_update_duck_vol_label)
        self.tts_vol_slider.valueChanged.connect(_update_duck_vol_label)
        self.tts_duck_vol_slider.valueChanged.connect(self._on_change)

        duck_vol_layout.addWidget(self.tts_duck_vol_label)
        duck_vol_layout.addWidget(self.tts_duck_vol_slider)
        duck_vol_layout.addWidget(self.tts_duck_vol_val_label)
        tts_layout.addLayout(duck_vol_layout)

        duck_probe_layout = QHBoxLayout()
        self.tts_duck_release_label = QLabel("Probing / release time:")
        self.tts_duck_release_spin = QSpinBox()
        self.tts_duck_release_spin.setRange(20, 500)
        self.tts_duck_release_spin.setSingleStep(10)
        self.tts_duck_release_spin.setValue(self.config.get("tts_duck_release_ms", 80))
        self.tts_duck_release_spin.setSuffix(" ms")
        self.tts_duck_release_spin.setToolTip(
            "How long to keep TTS ducked after voice audio drops below threshold. Recommended for testing: 60-100 ms."
        )
        self.tts_duck_release_spin.valueChanged.connect(self._on_change)
        self.duck_probe_hint_label = QLabel("(Recommended: 60–100 ms, test)")
        self.duck_probe_hint_label.setStyleSheet("color: gray; font-size: 11px;")

        duck_probe_layout.addWidget(self.tts_duck_release_label)
        duck_probe_layout.addWidget(self.tts_duck_release_spin)
        duck_probe_layout.addWidget(self.duck_probe_hint_label)
        duck_probe_layout.addStretch()

        self.tts_duck_test_btn = QPushButton("Test Ducking")
        self.tts_duck_test_btn.setToolTip(
            "Plays a test announcement and simulates someone speaking in the middle so you can hear the ducking level."
        )
        self.tts_duck_test_btn.clicked.connect(self._test_ducking)
        duck_probe_layout.addWidget(self.tts_duck_test_btn)

        tts_layout.addLayout(duck_probe_layout)

        def _sync_duck_enabled(*_):
            from tts_manager import find_audio_player, supports_live_ducking
            enabled = self.tts_checkbox.isChecked()
            pref = self.tts_player_combo.currentData() if hasattr(self, "tts_player_combo") else self.config.get("tts_audio_player", "auto")
            p_type, _ = find_audio_player(pref)
            supported = supports_live_ducking(p_type)
            duck_on = enabled and supported and self.tts_duck_checkbox.isChecked()
            self.tts_duck_checkbox.setEnabled(enabled and supported)
            self.tts_duck_vol_slider.setEnabled(duck_on)
            self.tts_duck_release_spin.setEnabled(duck_on)
            self.tts_duck_test_btn.setEnabled(duck_on)
            if not supported:
                self.tts_duck_checkbox.setToolTip(
                    "Live ducking is not supported for the selected audio player (requires mpv or pactl on Linux, or win32_mci on Windows)."
                )
            else:
                self.tts_duck_checkbox.setToolTip(
                    "Lowers TTS volume when a user on the userlist is talking and audio is actually detected from the VoIP app (ignores silent PTT key-up)."
                )

        _sync_duck_enabled()
        self.tts_checkbox.toggled.connect(_sync_duck_enabled)
        self.tts_duck_checkbox.toggled.connect(_sync_duck_enabled)
        if hasattr(self, "tts_player_combo"):
            self.tts_player_combo.currentIndexChanged.connect(_sync_duck_enabled)
        
        # Cache controls
        tts_cache_layout = QHBoxLayout()
        from tts_manager import get_tts_manager
        tts_manager = get_tts_manager(self.config)
        size_mb = tts_manager.get_cache_size()
        self._last_cache_size_mb = size_mb
        
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
        cache_path = get_tts_manager(self.config).cache_dir
        self._cache_path_str = cache_path
        self.cache_path_label = QLabel(f"<span style='color: gray; font-size: 10px;'>Path: {cache_path}</span>")
        tts_layout.addWidget(self.cache_path_label)
        
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
            
        monitors_layout.addStretch()
        self.reset_positions_btn = QPushButton("Reset overlay positions")
        self.reset_positions_btn.setToolTip("Place all overlays side-by-side in the center of the primary monitor.")
        self.reset_positions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_positions_btn.clicked.connect(self._on_reset_positions_clicked)
        monitors_layout.addWidget(self.reset_positions_btn)
            
        monitors_group_layout.addLayout(monitors_layout)

        # Polling and Width Settings
        width_layout = QHBoxLayout()
        
        # Poll interval
        self.poll_label = QLabel("Active Window Check Interval:")
        self.poll_slider = QSlider(Qt.Orientation.Horizontal)
        min_poll = 50 if sys.platform == "win32" else 200
        self.poll_slider.setMinimum(min_poll)
        self.poll_slider.setMaximum(1000)
        self.poll_slider.setSingleStep(50)
        self.poll_slider.setTickInterval(50)
        self.poll_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        def on_poll_slider_changed(val):
            snapped = max(min_poll, round(val / 50) * 50)
            if snapped != val:
                self.poll_slider.blockSignals(True)
                self.poll_slider.setValue(snapped)
                self.poll_slider.blockSignals(False)
            self.poll_val_label.setText(f"{snapped} ms")
            self._on_change()
            
        self.poll_slider.valueChanged.connect(on_poll_slider_changed)
        
        current_poll = max(min_poll, self.config.get("polling_interval_ms", 250))
        self.poll_val_label = QLabel(f"{current_poll} ms")
        self.poll_val_label.setMinimumWidth(60)
        self.poll_slider.blockSignals(True)
        self.poll_slider.setValue(current_poll)
        self.poll_slider.blockSignals(False)
        
        width_layout.addWidget(self.poll_label)
        width_layout.addWidget(self.poll_slider)
        width_layout.addWidget(self.poll_val_label)
        width_layout.addSpacing(20)
        
        # Dynamic width + right-anchor sub-option
        dyn_width_col = QVBoxLayout()
        dyn_width_col.setContentsMargins(0, 0, 0, 0)
        dyn_width_col.setSpacing(2)

        self.dynamic_width_checkbox = QCheckBox("Dynamic Width (fit to text)")
        self.dynamic_width_checkbox.setChecked(self.config.get("dynamic_width", True))
        self.dynamic_width_checkbox.toggled.connect(self._on_change)

        self.dynamic_width_right_anchor_checkbox = QCheckBox("Anchor right edge (shift left)")
        self.dynamic_width_right_anchor_checkbox.setToolTip(
            "Keep the right edge of the overlay fixed while keeping nicknames left-aligned.\n"
            "The entire text block shifts left/right depending on the width of the longest nickname."
        )
        self.dynamic_width_right_anchor_checkbox.setChecked(self.config.get("dynamic_width_right_anchor", False))
        self.dynamic_width_right_anchor_checkbox.setEnabled(self.dynamic_width_checkbox.isChecked())
        self.dynamic_width_right_anchor_checkbox.toggled.connect(self._on_change)
        self.dynamic_width_checkbox.toggled.connect(self.dynamic_width_right_anchor_checkbox.setEnabled)

        sub_opt_layout = QHBoxLayout()
        sub_opt_layout.setContentsMargins(18, 0, 0, 0)
        sub_opt_layout.setSpacing(0)
        sub_opt_layout.addWidget(self.dynamic_width_right_anchor_checkbox)

        dyn_width_col.addWidget(self.dynamic_width_checkbox)
        dyn_width_col.addLayout(sub_opt_layout)
        
        self.fixed_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.fixed_width_slider.setRange(50, 1000)
        self.fixed_width_slider.setValue(self.config.get("fixed_width", 200))
        self.fixed_width_val_label = QLabel(f"{self.fixed_width_slider.value()}px")
        self.fixed_width_slider.valueChanged.connect(lambda v: self.fixed_width_val_label.setText(f"{v}px"))
        self.fixed_width_slider.valueChanged.connect(self._on_change)
        
        self.fixed_width_slider.setEnabled(not self.dynamic_width_checkbox.isChecked())
        self.dynamic_width_checkbox.toggled.connect(lambda checked: self.fixed_width_slider.setEnabled(not checked))
        
        width_layout.addLayout(dyn_width_col)
        self.fixed_width_label = QLabel("Fixed Width:")
        width_layout.addWidget(self.fixed_width_label)
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
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(self.config.get("font_size", 11))
        self.font_size.valueChanged.connect(self._on_font_changed)

        self.line_height_spin = LineHeightSpinBox(self._get_default_line_height)
        self.line_height_spin.setRange(0, 150)
        self.line_height_spin.setSuffix(" px")
        self._update_line_height_special_value()
        self.line_height_spin.setValue(self.config.get("line_height", 0))
        self.line_height_spin.valueChanged.connect(self._on_change)

        self.font_label = QLabel("Font:")
        font_layout.addWidget(self.font_label)
        font_layout.addWidget(self.font_combo)
        self.font_size_label = QLabel("Size:")
        font_layout.addWidget(self.font_size_label)
        font_layout.addWidget(self.font_size)
        self.line_height_label = QLabel("Line height:")
        font_layout.addWidget(self.line_height_label)
        font_layout.addWidget(self.line_height_spin)
        self.line_height_auto_btn = QPushButton("Auto")
        self.line_height_auto_btn.setToolTip("Reset line height to Auto (calculated dynamically from font size)")
        self.line_height_auto_btn.clicked.connect(lambda: self.line_height_spin.setValue(0))
        font_layout.addWidget(self.line_height_auto_btn)
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
        
        self.text_color_whisper_btn = QPushButton("Choose Text Color (Whisper)")
        val_whisper = self.config.get("text_color_whisper", "#ff9900")
        if val_whisper.startswith("rgba"): val_whisper = "#ff9900"
        self.current_text_color_whisper = val_whisper
        self._update_text_color_whisper_btn()
        self.text_color_whisper_btn.clicked.connect(self._choose_text_color_whisper)
        color_layout.addWidget(self.text_color_whisper_btn)
        
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
        
        # Only wrap full-width banner/note labels (never short inline row labels)
        self.retranslate_ui()

        self.scroll_area.setWidget(self.container_widget)
        self.main_layout.addWidget(self.scroll_area)

        self._fit_window_to_content()
        
        # Prevent accidental scrolling changes
        self.scroll_filter = ScrollFilter(self)
        for child in self.container_widget.findChildren(QWidget):
            if isinstance(child, (QSlider, QSpinBox, QComboBox)):
                child.installEventFilter(self.scroll_filter)
                # Only allow wheel scroll when the user specifically clicks and focuses on the widget
                child.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Listen to system color scheme changes (Windows 10/11 & Linux)
        try:
            hints = QApplication.styleHints()
            if hasattr(hints, 'colorSchemeChanged'):
                hints.colorSchemeChanged.connect(self._update_banner_style)
        except Exception:
            pass

    def _is_dark_theme(self) -> bool:
        """
        Determines whether the window is currently rendering in a dark theme.
        Directly inspects the actual widget palette luminance rather than OS-level
        hints, because on Windows Qt widgets often render in light mode even when
        the OS taskbar/shell is dark.
        """
        try:
            # 1. Inspect actual widget palette
            window_col = self.palette().color(QPalette.ColorRole.Window)
            text_col = self.palette().color(QPalette.ColorRole.WindowText)

            # If default text in this window is dark (black/gray), the window is LIGHT!
            if text_col.lightness() < 128:
                return False

            # If window background is bright (white/light gray), the window is LIGHT!
            if window_col.lightness() >= 128:
                return False

            # If text is brighter than window background, it is DARK!
            return text_col.lightness() > window_col.lightness()
        except Exception:
            pass

        # Fallback to style hints only if palette inspection fails
        try:
            hints = QApplication.styleHints()
            if hasattr(hints, 'colorScheme'):
                return hints.colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            pass

        return False

    def _update_banner_style(self, *args):
        try:
            if not hasattr(self, 'banner_label'):
                return
            if self._is_dark_theme():
                bg_col = "rgba(30, 144, 255, 0.18)"
                text_col = "#ffffff"
                border_col = "rgba(59, 130, 246, 0.55)"
            else:
                bg_col = "#dbeafe"
                text_col = "#1e3a8a"
                border_col = "#3b82f6"

            self.banner_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_col};
                    color: {text_col};
                    border: 1px solid {border_col};
                    border-radius: 6px;
                    padding: 10px 14px;
                    font-size: 11pt;
                }}
            """)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        try:
            import theme_manager
            theme_manager.apply_window_theme(self)
        except Exception:
            pass

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            if event.type() in (
                QEvent.Type.PaletteChange,
                QEvent.Type.ApplicationPaletteChange,
                QEvent.Type.StyleChange
            ):
                self._update_banner_style()
        except Exception:
            pass

    def accept(self):
        self.finished.emit(1)
        self.closed.emit()
        self.close()

    def reject(self):
        self.finished.emit(0)
        self.closed.emit()
        self.close()

    def setModal(self, modal=False):
        pass

    def closeEvent(self, event):
        self._is_closing = True
        from PyQt6.QtCore import QTimer
        for timer in self.findChildren(QTimer):
            timer.stop()
        if hasattr(self, '_auth_thread') and self._auth_thread is not None and self._auth_thread.isRunning():
            self._auth_thread.cancel()
        self.finished.emit(0)
        self.closed.emit()
        super().closeEvent(event)

    def _schedule_ui_timer(self, delay_ms: int, callback):
        """Schedule a single-shot timer bound to this window's lifetime."""
        from PyQt6.QtCore import QTimer
        from PyQt6 import sip

        timer = QTimer(self)
        timer.setSingleShot(True)

        def _on_timeout():
            if not getattr(self, "_is_closing", False) and not sip.isdeleted(self):
                callback()
            if not sip.isdeleted(timer):
                timer.deleteLater()

        timer.timeout.connect(_on_timeout)
        timer.start(delay_ms)
        return timer

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

    def _update_text_color_whisper_btn(self):
        c = QColor(self.current_text_color_whisper)
        text_col = 'white' if c.lightness() < 128 else 'black'
        self.text_color_whisper_btn.setStyleSheet(f"background-color: {self.current_text_color_whisper}; color: {text_col};")

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
            
    def _choose_text_color_whisper(self):
        color = QColorDialog.getColor(QColor(self.current_text_color_whisper), self, "Select Text Color (Whisper)", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_text_color_whisper = color.name(QColor.NameFormat.HexArgb)
            self._update_text_color_whisper_btn()
            self._on_change()
            
    def _choose_text_color_left(self):
        color = QColorDialog.getColor(QColor(self.current_text_color_left), self, "Select Text Color (Left)", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.current_text_color_left = color.name(QColor.NameFormat.HexArgb)
            self._update_text_color_left_btn()
            self._on_change()
            
    def _sync_backend_widgets(self):
        if hasattr(self, 'ts3_widget') and hasattr(self, 'backend_ts3_radio'):
            self.ts3_widget.setVisible(self.backend_ts3_radio.isChecked())
        if hasattr(self, 'mumble_widget') and hasattr(self, 'backend_mumble_radio'):
            self.mumble_widget.setVisible(self.backend_mumble_radio.isChecked())
        if hasattr(self, 'discord_widget') and hasattr(self, 'backend_discord_radio'):
            self.discord_widget.setVisible(self.backend_discord_radio.isChecked())
            self._update_discord_ui()

    def _update_discord_ui(self):
        from i18n import tr
        if hasattr(self, 'discord_status_label') and hasattr(self, 'discord_auth_btn'):
            token = self.config.get("discord_access_token", "")
            if token:
                self.discord_status_label.setText(tr("settings.discord_status_auth", "Discord: Authorized (Local IPC)"))
                self.discord_auth_btn.setText(tr("settings.discord_btn_unauth", "Unauthorize Discord"))
                self.discord_auth_btn.setEnabled(True)
                if hasattr(self, 'discord_reauth_btn'):
                    self.discord_reauth_btn.setVisible(True)
                    self.discord_reauth_btn.setEnabled(True)
            else:
                self.discord_status_label.setText(tr("settings.discord_status_unauth", "Discord: Not authorized"))
                self.discord_auth_btn.setText(tr("settings.discord_btn_auth", "Authorize Discord"))
                self.discord_auth_btn.setEnabled(True)
                if hasattr(self, 'discord_reauth_btn'):
                    self.discord_reauth_btn.setVisible(False)

    def _on_backend_toggled(self, checked=True):
        if not checked:
            return
        self._sync_backend_widgets()
        self._on_change()

    def set_active_platform(self, platform):
        if hasattr(self, 'backend_ts3_radio'):
            self.backend_ts3_radio.blockSignals(True)
            self.backend_mumble_radio.blockSignals(True)
            self.backend_discord_radio.blockSignals(True)
            if platform == "discord":
                self.backend_discord_radio.setChecked(True)
            elif platform == "mumble":
                self.backend_mumble_radio.setChecked(True)
            else:
                self.backend_ts3_radio.setChecked(True)
            self.backend_ts3_radio.blockSignals(False)
            self.backend_mumble_radio.blockSignals(False)
            self.backend_discord_radio.blockSignals(False)
            self._sync_backend_widgets()

    def _on_discord_auth_btn_clicked(self):
        from i18n import tr
        token = self.config.get("discord_access_token", "")
        if token:
            reply = QMessageBox.question(
                self,
                tr("settings.discord_dlg_unauth_title", "Unauthorize Discord"),
                tr(
                    "settings.discord_dlg_unauth_msg",
                    "Are you sure you want to unauthorize Discord?<br><br>"
                    "This will disconnect KOverlay from Discord and clear the saved authorization token.",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.config["discord_access_token"] = ""
                self._on_change()
                self._update_discord_ui()
                QMessageBox.information(
                    self,
                    tr("settings.discord_dlg_unauth_done_title", "Discord Unauthorized"),
                    tr("settings.discord_dlg_unauth_done_msg", "Discord access token has been cleared successfully."),
                )
        else:
            self._start_discord_authorization()

    def _start_discord_authorization(self):
        from discord_client import DiscordAuthThread
        from i18n import tr
        self.discord_auth_btn.setEnabled(False)
        if hasattr(self, 'discord_reauth_btn'):
            self.discord_reauth_btn.setEnabled(False)
        self.discord_auth_btn.setText(tr("settings.discord_btn_authorizing", "Authorizing... (Check Discord)"))
        self.discord_status_label.setText(tr("settings.discord_status_waiting", "Discord: Waiting for authorization in Discord..."))

        if hasattr(self, '_auth_thread') and self._auth_thread is not None and self._auth_thread.isRunning():
            self._auth_thread.cancel()

        self._auth_thread = DiscordAuthThread(
            client_id=self.config.get("discord_client_id", "207646673902501888"),
            parent=self
        )
        self._auth_thread.auth_success.connect(self._on_discord_auth_success)
        self._auth_thread.auth_failed.connect(self._on_discord_auth_failed)
        self._auth_thread.start()

    def _on_discord_auth_success(self, token):
        from PyQt6 import sip
        from i18n import tr
        if getattr(self, "_is_closing", False) or sip.isdeleted(self):
            return
        self.config["discord_access_token"] = token
        self._on_change()
        self._update_discord_ui()
        QMessageBox.information(
            self,
            tr("settings.discord_dlg_auth_ok_title", "Discord Authorized"),
            tr("settings.discord_dlg_auth_ok_msg", "Discord authorization successful!<br>KOverlay is now connected to Discord."),
        )

    def _on_discord_auth_failed(self, error_msg):
        from PyQt6 import sip
        from i18n import tr
        if getattr(self, "_is_closing", False) or sip.isdeleted(self):
            return
        self._update_discord_ui()
        QMessageBox.warning(
            self,
            tr("settings.discord_dlg_auth_fail_title", "Discord Authorization Failed"),
            tr("settings.discord_dlg_auth_fail_msg", "Could not authorize Discord:<br><br>{error}", error=error_msg),
        )

    def _install_mumble_plugin(self):
        if sys.platform == "win32":
            app_dir = os.path.dirname(os.path.abspath(__file__))
            candidate_paths = [
                os.path.join(app_dir, "mumble_plugin", "koverlay_mumble.dll"),
                os.path.join(app_dir, "koverlay_mumble.dll")
            ]
            src_dll = next((p for p in candidate_paths if os.path.isfile(p)), None)

            # Modern Mumble (Qt AppDataLocation) scans %APPDATA%\Mumble\Mumble\Plugins
            # Legacy/custom configurations scan %APPDATA%\Mumble\Plugins
            target_dirs = [
                os.path.expandvars(r"%APPDATA%\Mumble\Mumble\Plugins"),
                os.path.expandvars(r"%APPDATA%\Mumble\Plugins"),
                os.path.expandvars(r"%LOCALAPPDATA%\Mumble\Mumble\Plugins"),
            ]

            installed_destinations = []
            if src_dll:
                for target_dir in target_dirs:
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                        dest_dll = os.path.join(target_dir, "koverlay_mumble.dll")
                        shutil.copy2(src_dll, dest_dll)
                        installed_destinations.append(dest_dll)
                    except Exception:
                        pass

                # Also copy .mumble_plugin bundle if present
                bundle_src = os.path.join(app_dir, "mumble_plugin", "koverlay_mumble.mumble_plugin")
                if os.path.isfile(bundle_src):
                    for target_dir in target_dirs:
                        try:
                            shutil.copy2(bundle_src, os.path.join(target_dir, "koverlay_mumble.mumble_plugin"))
                        except Exception:
                            pass

                primary_dir = target_dirs[0]
                msg = (
                    "<b>KOverlay Mumble Plugin successfully installed!</b><br><br>"
                    "The plugin was automatically deployed to Mumble's plugin directories:<br>"
                    f"&bull; <code>{target_dirs[0]}</code><br>"
                    f"&bull; <code>{target_dirs[1]}</code><br><br>"
                    "<b>Next steps:</b><br>"
                    "1. If Mumble is running, restart it or open <b>Configure &rarr; Settings &rarr; Plugins</b>.<br>"
                    "2. Ensure <b>KOverlay Mumble Plugin</b> is checked and enabled.<br>"
                    "3. Click <b>Apply</b>.<br><br>"
                    "<i>Would you like to open the Mumble Plugins directory in Windows Explorer?</i>"
                )
                reply = QMessageBox.information(
                    self,
                    "Mumble Plugin Installed (Windows)",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(primary_dir))
                return

            # Fallback if bundled DLL is missing
            msg = (
                "<b>koverlay_mumble.dll was not found in your KOverlay installation directory.</b><br><br>"
                f"Searched in:<br><code>{candidate_paths[0]}</code><br><br>"
                "You can download <code>koverlay_mumble.dll</code> directly from the KOverlay GitHub repository:<br>"
                "<a href='https://github.com/Arkanista/KOverlay/releases/latest'>https://github.com/Arkanista/KOverlay/releases/latest</a><br><br>"
                f"And place it into your Mumble plugins folder:<br><code>{plugins_dir}</code><br><br>"
                "<i>Would you like to open the Mumble Plugins folder in Windows Explorer now?</i>"
            )
            reply = QMessageBox.information(
                self,
                "Mumble Plugin Setup (Windows)",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(plugins_dir))
            return

        plugin_script = os.path.join(os.path.dirname(__file__), "mumble_plugin", "build_and_install.sh")
        if not os.path.exists(plugin_script):
            QMessageBox.critical(self, "Error", f"Build script not found at:\n{plugin_script}")
            return
        try:
            res = subprocess.run(["bash", plugin_script], capture_output=True, text=True)
            if res.returncode == 0:
                QMessageBox.information(
                    self,
                    "Mumble Plugin Installed",
                    "KOverlay Mumble Plugin successfully built and installed!\n\n"
                    "Next step:\n"
                    "1. Open Mumble\n"
                    "2. Go to: Configure -> Settings -> Plugins\n"
                    "3. Ensure 'KOverlay Mumble Plugin' is enabled."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Installation Failed",
                    f"Failed to build/install plugin:\n\n{res.stderr or res.stdout}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute build script:\n{e}")

    def _on_reset_positions_clicked(self):
        self.reset_positions_requested.emit()
        self.reset_positions_btn.setText("Positions Reset! ✓")
        from PyQt6 import sip
        def _restore_reset_btn():
            if hasattr(self, "reset_positions_btn") and not sip.isdeleted(self.reset_positions_btn):
                self.reset_positions_btn.setText("Reset overlay positions")
        self._schedule_ui_timer(2000, _restore_reset_btn)

    def _get_default_line_height(self) -> int:
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size.value())
        font.setBold(True)
        fm = QFontMetrics(font)
        return max(fm.lineSpacing(), 12)

    def _update_line_height_special_value(self):
        def_h = self._get_default_line_height()
        self.line_height_spin.setSpecialValueText(f"Auto ({def_h} px)")

    def _on_font_changed(self):
        self._update_line_height_special_value()
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
            
        if hasattr(self, 'backend_discord_radio') and self.backend_discord_radio.isChecked():
            self.config["voice_backend"] = "discord"
        elif hasattr(self, 'backend_mumble_radio') and self.backend_mumble_radio.isChecked():
            self.config["voice_backend"] = "mumble"
        else:
            self.config["voice_backend"] = "ts3"
        if hasattr(self, 'mumble_port_spin'):
            self.config["mumble_port"] = self.mumble_port_spin.value()
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["game_only"] = self.game_only_checkbox.isChecked()
        self.config["hide_delay_enabled"] = self.hide_delay_checkbox.isChecked()
        self.config["hide_delay_seconds"] = self.hide_delay_slider.value()
        self.config["target_keywords"] = [k.strip() for k in self.keywords_input.text().split(",") if k.strip()]
        self.config["polling_interval_ms"] = self.poll_slider.value()
        self.config["opacity_normal"] = self.opacity_normal_slider.value() / 100.0
        self.config["opacity_move"] = self.opacity_move_slider.value() / 100.0
        self.config["dynamic_width"] = self.dynamic_width_checkbox.isChecked()
        if hasattr(self, 'dynamic_width_right_anchor_checkbox'):
            self.config["dynamic_width_right_anchor"] = self.dynamic_width_right_anchor_checkbox.isChecked()
        self.config["fixed_width"] = self.fixed_width_slider.value()
        if "opacity" in self.config:
            del self.config["opacity"]
        self.config["font_family"] = self.font_combo.currentFont().family()
        self.config["font_size"] = self.font_size.value()
        self.config["line_height"] = self.line_height_spin.value()
        self.config["bg_color"] = self.current_bg_color
        self.config["text_color_normal"] = self.current_text_color_normal
        self.config["text_color_talking"] = self.current_text_color_talking
        self.config["text_color_whisper"] = self.current_text_color_whisper
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
        if hasattr(self, 'language_combo'):
            self.config["language"] = self.language_combo.currentData()
        if hasattr(self, 'tts_duck_checkbox'):
            self.config["tts_ducking_enabled"] = self.tts_duck_checkbox.isChecked()
        if hasattr(self, 'tts_duck_vol_slider'):
            self.config["tts_duck_volume_pct"] = self.tts_duck_vol_slider.value()
        if hasattr(self, 'tts_duck_release_spin'):
            self.config["tts_duck_release_ms"] = self.tts_duck_release_spin.value()
        if hasattr(self, 'tts_player_combo'):
            self.config["tts_audio_player"] = self.tts_player_combo.currentData()
        
        if self.cache_retention_checkbox.isChecked():
            self.config["tts_cache_retention_days"] = self.cache_retention_spin.value()
        else:
            self.config["tts_cache_retention_days"] = 0
            
        self.config["history_duration"] = self.history_dur_slider.value()

        if hasattr(self, 'sort_order_combo'):
            chosen_sort = self.sort_order_combo.currentData()
            self.config["sort_order"] = chosen_sort
            self.config["recent_speakers_first"] = (chosen_sort == "recent_speakers")
        elif hasattr(self, 'recent_speakers_checkbox'):
            self.config["recent_speakers_first"] = self.recent_speakers_checkbox.isChecked()
        if hasattr(self, 'speaker_fade_slider'):
            self.config["speaker_fade_duration"] = self.speaker_fade_slider.value()
        if hasattr(self, 'limit_users_checkbox'):
            self.config["limit_users_enabled"] = self.limit_users_checkbox.isChecked()
        if hasattr(self, 'limit_users_input'):
            self.config["limit_users_count"] = self.limit_users_input.text().strip()
        if hasattr(self, 'strip_brackets_checkbox'):
            self.config["strip_bracket_tags"] = self.strip_brackets_checkbox.isChecked()
        if hasattr(self, 'discord_icons_checkbox'):
            self.config["discord_show_status_icons"] = self.discord_icons_checkbox.isChecked()
        if hasattr(self, 'discord_icons_pos_combo'):
            self.config["discord_status_icons_position"] = self.discord_icons_pos_combo.currentData()
        if hasattr(self, 'tts_lowercase_checkbox'):
            self.config["tts_lowercase"] = self.tts_lowercase_checkbox.isChecked()
        if hasattr(self, 'tts_replace_digits_checkbox'):
            self.config["tts_replace_digits"] = self.tts_replace_digits_checkbox.isChecked()

        # Emit signal to inform main app to apply changes
        self.config_changed.emit()
        
    def _open_digits_window(self):
        from digits_window import DigitsWindow
        dlg = DigitsWindow(self.config.get("tts_digit_replacements"), self)
        if dlg.exec() == DigitsWindow.Accepted:
            self.config["tts_digit_replacements"] = dlg.get_replacements()
            self._on_change()

    def _open_alias_window(self):
        from alias_window import AliasWindow
        dlg = AliasWindow(self.config.get("tts_aliases", {}), self)
        if dlg.exec() == AliasWindow.Accepted:
            self.config["tts_aliases"] = dlg.get_aliases()
            self._on_change()

    def _open_prefix_window(self):
        from prefix_window import PrefixWindow
        dlg = PrefixWindow(self.config.get("nickname_prefixes", []), self)
        if dlg.exec() == PrefixWindow.Accepted:
            self.config["nickname_prefixes"] = dlg.get_prefixes()
            count = len(self.config["nickname_prefixes"])
            self.prefix_count_label.setText(f"({count} custom)" if count > 0 else "")
            self._on_change()

    def retranslate_ui(self):
        from i18n import tr
        self.setWindowTitle(tr("settings.title", "KOverlay Settings"))
        if hasattr(self, 'banner_label'):
            self.banner_label.setText(tr("settings.banner_important", "ℹ️ <b>Important:</b> KOverlay must remain running in the background (system tray) for the overlay to appear."))
        if hasattr(self, 'general_group'):
            self.general_group.setTitle(tr("settings.group_general", "Voice Backend & Connection"))
        if hasattr(self, 'language_label'):
            self.language_label.setText(f"<b>{tr('settings.language', 'Language:')}</b>")
        if hasattr(self, 'open_locales_btn'):
            self.open_locales_btn.setText(tr("settings.open_locales_btn", "Open Locales Folder"))
        if hasattr(self, 'voice_platform_label'):
            self.voice_platform_label.setText(f"<b>{tr('settings.voice_platform', 'Voice Platform:')}</b>")
        if hasattr(self, 'ts3_key_label'):
            self.ts3_key_label.setText(tr("settings.ts3_api_key", "TS3 API Key:"))
        if hasattr(self, 'mumble_port_label'):
            self.mumble_port_label.setText(tr("settings.mumble_port", "Mumble IPC Port:"))
        if hasattr(self, 'backend_ts3_radio'):
            self.backend_ts3_radio.setText(tr("settings.backend_ts3", "TeamSpeak 3"))
        if hasattr(self, 'backend_mumble_radio'):
            self.backend_mumble_radio.setText(tr("settings.backend_mumble", "Mumble"))
        if hasattr(self, 'backend_discord_radio'):
            self.backend_discord_radio.setText(tr("settings.backend_discord", "Discord"))
        if hasattr(self, 'mumble_install_btn'):
            self.mumble_install_btn.setText(tr("settings.mumble_install_btn", "Install / Recompile Mumble Plugin"))
        if hasattr(self, 'discord_reauth_btn'):
            self.discord_reauth_btn.setText(tr("settings.discord_btn_reauth", "Re-authorize"))
        self._update_discord_ui()
        if hasattr(self, 'discord_icons_checkbox'):
            self.discord_icons_checkbox.setText(tr("settings.discord_show_icons", "Show status icons (mute, deafen, etc.)"))
        if hasattr(self, 'discord_icons_side_label'):
            self.discord_icons_side_label.setText(tr("settings.discord_icons_side", "Icons side:"))
        if hasattr(self, 'discord_icons_pos_combo'):
            side_texts = {
                "right": tr("settings.discord_icons_right", "Right of nickname (Default)"),
                "left": tr("settings.discord_icons_left", "Left of nickname"),
            }
            for i in range(self.discord_icons_pos_combo.count()):
                d_val = self.discord_icons_pos_combo.itemData(i)
                if d_val in side_texts:
                    self.discord_icons_pos_combo.setItemText(i, side_texts[d_val])
        if hasattr(self, 'game_only_checkbox'):
            self.game_only_checkbox.setText(tr("settings.game_only", "Show ONLY when game is active"))
        if hasattr(self, 'hide_delay_checkbox'):
            self.hide_delay_checkbox.setText(tr("settings.hide_delay", "Delay hiding when game loses focus"))
        if hasattr(self, 'keywords_label'):
            self.keywords_label.setText(tr("settings.target_keywords", "Target Window Keywords (comma separated):"))
        if hasattr(self, 'history_group'):
            self.history_group.setTitle(tr("settings.group_history", "Join/Leave History"))
        if hasattr(self, 'history_checkbox'):
            self.history_checkbox.setText(tr("settings.history_enable", "Enable Join/Leave History (🡅 / 🡇 indicators)"))
        if hasattr(self, 'history_dur_label'):
            self.history_dur_label.setText(tr("settings.history_duration", "Duration:"))
        if hasattr(self, 'speakers_group'):
            self.speakers_group.setTitle(tr("settings.group_speakers", "User List & Speaking Behavior"))
        if hasattr(self, 'sorting_label'):
            self.sorting_label.setText(tr("settings.user_sorting", "User list sorting:"))
        if hasattr(self, 'sort_order_combo'):
            sort_texts = {
                "alphabetical_fading_top": tr("settings.sort_alpha_fading", "Alphabetical (recent speakers on top while fading)"),
                "recent_speakers": tr("settings.sort_recent_top", "Recent speakers on top (most recent first)"),
                "alphabetical": tr("settings.sort_alpha_inplace", "Alphabetical (speakers in-place)"),
            }
            for i in range(self.sort_order_combo.count()):
                key_data = self.sort_order_combo.itemData(i)
                if key_data in sort_texts:
                    self.sort_order_combo.setItemText(i, sort_texts[key_data])
        if hasattr(self, 'limit_users_checkbox'):
            self.limit_users_checkbox.setText(tr("settings.limit_users", "Limit user list to:"))
        if hasattr(self, 'users_suffix_label'):
            self.users_suffix_label.setText(tr("settings.users_suffix", "users"))
        if hasattr(self, 'sort_note_label'):
            self.sort_note_label.setText(f"<span style='color: gray; font-size: 11px;'>{tr('settings.sort_note', 'Note: Users who left the channel are always placed at the bottom of the list.')}</span>")
        if hasattr(self, 'fade_label'):
            self.fade_label.setText(tr("settings.fade_duration", "Keep recent speakers highlighted (fade duration):"))
        if hasattr(self, 'strip_brackets_checkbox'):
            self.strip_brackets_checkbox.setText(tr("settings.strip_brackets", "Remove all bracket tags ([...], (...), {...})"))
        if hasattr(self, 'nick_prefix_btn'):
            self.nick_prefix_btn.setText(tr("settings.nick_prefixes_btn", "Nick Prefixes..."))
        if hasattr(self, 'tts_group'):
            self.tts_group.setTitle(tr("settings.group_tts", "Text-to-Speech (TTS)"))
        if hasattr(self, 'tts_checkbox'):
            self.tts_checkbox.setText(tr("settings.tts_enable", "Enable TTS voice announcements"))
        if hasattr(self, 'tts_engine_label'):
            self.tts_engine_label.setText(tr("settings.tts_audio_engine", "Audio Engine (Linux):"))
        if hasattr(self, 'tts_player_combo'):
            desc_keys = {
                "mpv": ("settings.engine_desc_mpv", "mpv ★ Recommended (gapless silence removal)"),
                "ffplay": ("settings.engine_desc_ffplay", "ffplay ★ Recommended (gapless silence removal)"),
                "pw-play": ("settings.engine_desc_pw_play", "pw-play ● Standard (PipeWire native, no silence trim)"),
                "paplay": ("settings.engine_desc_paplay", "paplay ○ Fallback (PulseAudio, no silence trim)"),
                "gst-play-1.0": ("settings.engine_desc_gst", "gst-play-1.0 ○ Fallback (GStreamer, higher latency)"),
                "cvlc": ("settings.engine_desc_cvlc", "cvlc ○ Fallback (VLC CLI, higher overhead)"),
            }
            from tts_manager import find_available_audio_players
            avail = find_available_audio_players()
            best_auto = avail[0][0] if avail else "none"
            bin_map = dict(avail)
            for i in range(self.tts_player_combo.count()):
                p_val = self.tts_player_combo.itemData(i)
                if p_val == "auto":
                    self.tts_player_combo.setItemText(
                        i,
                        tr("settings.tts_engine_auto", "Auto (Best detected: {engine})", engine=best_auto),
                    )
                elif p_val in desc_keys:
                    k, default_desc = desc_keys[p_val]
                    p_bin = bin_map.get(p_val, "")
                    suffix = f"  [{p_bin}]" if p_bin else ""
                    self.tts_player_combo.setItemText(i, f"{tr(k, default_desc)}{suffix}")
        if hasattr(self, 'tts_player_info_btn'):
            self.tts_player_info_btn.setText(tr("settings.tts_which_engine", "Which engine is best?"))
        if hasattr(self, 'tts_join_checkbox'):
            self.tts_join_checkbox.setText(tr("settings.tts_join", "Announce Join:"))
        if hasattr(self, 'tts_leave_checkbox'):
            self.tts_leave_checkbox.setText(tr("settings.tts_leave", "Announce Leave:"))
        if hasattr(self, 'var_info_label'):
            self.var_info_label.setText(tr("settings.tts_var_info", "Use %NICK in the text above to insert the user's name."))
        if hasattr(self, 'tts_lowercase_checkbox'):
            self.tts_lowercase_checkbox.setText(tr("settings.tts_lowercase", "Convert to lowercase (better pronunciation of ALL-CAPS)"))
        if hasattr(self, 'tts_replace_digits_checkbox'):
            self.tts_replace_digits_checkbox.setText(tr("settings.tts_replace_digits", "Replace digits with letters (1337)"))
        if hasattr(self, 'tts_digits_btn'):
            self.tts_digits_btn.setText(tr("settings.tts_digits_btn", "Digit Substitutions..."))
        if hasattr(self, 'tts_alias_btn'):
            self.tts_alias_btn.setText(tr("settings.tts_alias_btn", "TTS Aliases..."))
        if hasattr(self, 'tts_delay_label'):
            self.tts_delay_label.setText(tr("settings.tts_delay", "Read Delay:"))
        if hasattr(self, 'tts_voice_label'):
            self.tts_voice_label.setText(tr("settings.tts_voice", "Voice:"))
        if hasattr(self, 'tts_speed_label'):
            self.tts_speed_label.setText(tr("settings.tts_speed", "Speed:"))
        if hasattr(self, 'tts_vol_label'):
            self.tts_vol_label.setText(tr("settings.tts_volume", "Volume:"))
        if hasattr(self, 'tts_duck_checkbox'):
            self.tts_duck_checkbox.setText(tr("settings.tts_duck_enable", "Duck TTS volume on actual speech (ignores silent key-up)"))
        if hasattr(self, 'tts_duck_vol_label'):
            self.tts_duck_vol_label.setText(tr("settings.tts_duck_volume", "Ducking volume:"))
        if hasattr(self, 'tts_duck_release_label'):
            self.tts_duck_release_label.setText(tr("settings.tts_duck_release", "Probing / release time:"))
        if hasattr(self, 'duck_probe_hint_label'):
            self.duck_probe_hint_label.setText(tr("settings.tts_duck_hint", "(Recommended: 60–100 ms, test)"))
        if hasattr(self, 'tts_duck_test_btn'):
            self.tts_duck_test_btn.setText(tr("settings.tts_duck_test_btn", "Test Ducking"))
        if hasattr(self, 'tts_test_btn'):
            self.tts_test_btn.setText(tr("settings.tts_test_btn", "Test"))
        if hasattr(self, 'tts_info_label'):
            if sys.platform == "win32":
                self.tts_info_label.setText(tr("settings.tts_note_win", "Note: Uses high-quality voices over the internet. Requires 'edge-tts' Python module (supports built-in Windows audio or mpv.exe)."))
            else:
                self.tts_info_label.setText(tr("settings.tts_note_linux", "Note: Uses high-quality voices over the internet. Requires 'edge-tts' and an audio player (mpv, ffplay, pw-play, paplay, or gst-play-1.0)."))
        if hasattr(self, 'cache_path_label'):
            p_str = getattr(self, '_cache_path_str', '')
            self.cache_path_label.setText(f"<span style='color: gray; font-size: 10px;'>{tr('settings.tts_cache_path', 'Path: {path}', path=p_str)}</span>")
        if hasattr(self, 'cache_size_label'):
            self.cache_size_label.setText(tr("settings.tts_cache_size", "Cache size: {size} MB", size=f"{getattr(self, '_last_cache_size_mb', 0.0):.2f}"))
        if hasattr(self, 'cache_retention_checkbox'):
            self.cache_retention_checkbox.setText(tr("settings.tts_auto_clear", "Auto-clear older than:"))
        if hasattr(self, 'clear_cache_btn'):
            self.clear_cache_btn.setText(tr("settings.tts_clear_cache", "Clear Cache"))
        if hasattr(self, 'open_cache_btn'):
            self.open_cache_btn.setText(tr("settings.tts_open_folder", "Open Folder"))
        if hasattr(self, 'monitors_group'):
            self.monitors_group.setTitle(tr("settings.group_overlays", "Overlays"))
        if hasattr(self, 'monitor_checkboxes'):
            for oid, cb in self.monitor_checkboxes.items():
                cb.setText(tr("settings.enable_overlay", "Enable Overlay {id}", id=oid))
        if hasattr(self, 'reset_positions_btn'):
            self.reset_positions_btn.setText(tr("settings.reset_positions", "Reset overlay positions"))
        if hasattr(self, 'poll_label'):
            self.poll_label.setText(tr("settings.poll_interval", "Active Window Check Interval:"))
        if hasattr(self, 'dynamic_width_checkbox'):
            self.dynamic_width_checkbox.setText(tr("settings.dynamic_width", "Dynamic Width (fit to text)"))
        if hasattr(self, 'dynamic_width_right_anchor_checkbox'):
            self.dynamic_width_right_anchor_checkbox.setText(tr("settings.anchor_right", "Anchor right edge (shift left)"))
        if hasattr(self, 'fixed_width_label'):
            self.fixed_width_label.setText(tr("settings.fixed_width", "Fixed Width:"))
        if hasattr(self, 'opacity_normal_label'):
            self.opacity_normal_label.setText(tr("settings.opacity_normal", "Background Opacity (Normal Mode):"))
        if hasattr(self, 'opacity_move_label'):
            self.opacity_move_label.setText(tr("settings.opacity_move", "Opacity (Move Mode):"))
        if hasattr(self, 'font_label'):
            self.font_label.setText(tr("settings.font", "Font:"))
        if hasattr(self, 'font_size_label'):
            self.font_size_label.setText(tr("settings.font_size", "Size:"))
        if hasattr(self, 'line_height_label'):
            self.line_height_label.setText(tr("settings.line_height", "Line height:"))
        if hasattr(self, 'line_height_auto_btn'):
            self.line_height_auto_btn.setText(tr("settings.line_height_auto", "Auto"))
        if hasattr(self, 'color_btn'):
            self.color_btn.setText(tr("settings.color_bg", "Choose Background Color"))
        if hasattr(self, 'text_color_normal_btn'):
            self.text_color_normal_btn.setText(tr("settings.color_normal", "Choose Text Color (Normal)"))
        if hasattr(self, 'text_color_talking_btn'):
            self.text_color_talking_btn.setText(tr("settings.color_talking", "Choose Text Color (Talking)"))
        if hasattr(self, 'text_color_whisper_btn'):
            self.text_color_whisper_btn.setText(tr("settings.color_whisper", "Choose Text Color (Whisper)"))
        if hasattr(self, 'text_color_left_btn'):
            self.text_color_left_btn.setText(tr("settings.color_left", "Choose Text Color (Left)"))
        if hasattr(self, 'header_checkbox'):
            self.header_checkbox.setText(tr("settings.show_header", "Show Title Header (Logo + Text)"))
        if hasattr(self, 'three_dots_checkbox'):
            self.three_dots_checkbox.setText(tr("settings.show_dots", "Show Dots Indicator (number of dots indicates ID number of overlay)"))
        if hasattr(self, 'disable_blink_checkbox'):
            self.disable_blink_checkbox.setText(tr("settings.disable_blink", "Disable border blinking on startup"))
        if hasattr(self, 'save_btn'):
            self.save_btn.setText(tr("settings.btn_close", "Close"))

    def _fit_window_to_content(self):
        if hasattr(self, 'container_widget'):
            self.container_widget.adjustSize()
            hint = self.container_widget.sizeHint()
            target_w = max(1040, min(hint.width() + 48, 1320))
            target_h = min(max(self.height(), hint.height() + 24), 820)
            self.setMinimumWidth(min(target_w, 1120))
            self.resize(target_w, target_h)

    def _on_language_changed(self):
        from i18n import set_language
        lang = self.language_combo.currentData()
        if lang:
            set_language(lang)
            self.retranslate_ui()
            self._fit_window_to_content()
        self._on_change()

    def _open_locales_folder(self):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        from i18n import USER_LOCALES_DIR, ensure_user_locales_populated
        ensure_user_locales_populated()
        QDesktopServices.openUrl(QUrl.fromLocalFile(USER_LOCALES_DIR))

    def _test_ducking(self):
        self._on_change()
        voice = self.tts_voice_combo.currentData()
        vol = self.tts_vol_slider.value()
        rate = self.tts_rate_combo.currentData()
        tts_mgr = get_tts_manager(self.config)
        tts_mgr.clear_queue()

        from audio_ducking import get_voip_audio_monitor
        monitor = get_voip_audio_monitor(self.config)
        monitor.schedule_test_duck_on_next_play(0.9, 1.8)

        # Start at full volume, duck for ~1.8s once playback starts, then return to normal
        test_text = "Testing voice ducking. Volume is lowered now, and should return to normal."
        tts_mgr.enqueue(text=test_text, voice=voice, volume=vol, delay=0, rate=rate)

    def _test_voice(self):
        voice = self.tts_voice_combo.currentData()
        vol = self.tts_vol_slider.value()
        join_txt = getattr(self, "tts_join_text", None)
        leave_txt = getattr(self, "tts_leave_text", None)
        j_t = join_txt.text() if join_txt else "%NICK joined"
        l_t = leave_txt.text() if leave_txt else "%NICK left"
        
        test_name = self.tts_test_nick.text() or "Arkanis"
        from tts_manager import prepare_tts_nickname
        spoken_name = prepare_tts_nickname(test_name, self.config)
        
        custom_text = f"{j_t.replace('%NICK', spoken_name)}. {l_t.replace('%NICK', spoken_name)}."
        
        delay = self.config.get("tts_delay_ms", 0) / 1000.0
        tts_mgr = get_tts_manager(self.config)
        tts_mgr.clear_queue()
        tts_mgr.enqueue(
            text=custom_text,
            voice=self.tts_voice_combo.currentData(),
            volume=self.tts_vol_slider.value(),
            delay=0, # No delay for test button
            rate=self.tts_rate_combo.currentData()
        )
        
        # Update cache size label after test (give worker time to download)
        from PyQt6 import sip
        def update_cache():
            if hasattr(self, "cache_size_label") and not sip.isdeleted(self.cache_size_label):
                size_mb = get_tts_manager().get_cache_size()
                self.cache_size_label.setText(f"Cache size: {size_mb:.2f} MB")
        # Poll a few times since TTS generation time varies
        self._schedule_ui_timer(2000, update_cache)
        self._schedule_ui_timer(5000, update_cache)
        self._schedule_ui_timer(10000, update_cache)

    def _open_cache_folder(self):
        cache_path = get_tts_manager(self.config).cache_dir
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
