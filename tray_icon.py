import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import pyqtSignal
from i18n import tr

class TrayIcon(QSystemTrayIcon):
    move_toggled = pyqtSignal(bool)
    mute_toggled = pyqtSignal(bool)
    overlay_toggled = pyqtSignal(str, bool)
    platform_changed = pyqtSignal(str)
    discord_reauthorize_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None, initial_mute=False, overlays_config=None, initial_platform="ts3"):
        super().__init__(parent)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.setIcon(QIcon(icon_path))
        self.setToolTip(tr("tray.tooltip_default", "KOverlay v1.2.5"))
        
        # Create menu
        self.menu = QMenu()
        
        self.move_action = self.menu.addAction(tr("tray.move_overlays", "Move Overlays"))
        self.move_action.setCheckable(True)
        self.move_action.toggled.connect(self.move_toggled.emit)
        
        self.mute_action = self.menu.addAction(tr("tray.mute_tts", "Mute TTS Voice"))
        self.mute_action.setCheckable(True)
        self.mute_action.setChecked(initial_mute)
        self.mute_action.toggled.connect(self.mute_toggled.emit)
        
        self.menu.addSeparator()
        
        self.overlay_actions = {}
        if overlays_config is None:
            overlays_config = {}
            
        for o_id in ["1", "2", "3", "4"]:
            cfg = overlays_config.get(o_id, {})
            action = self.menu.addAction(tr("tray.show_overlay", "Show Overlay {id}", id=o_id))
            action.setCheckable(True)
            action.setChecked(cfg.get("enabled", False))
            action.toggled.connect(lambda checked, oid=o_id: self.overlay_toggled.emit(oid, checked))
            self.overlay_actions[o_id] = action

        self.menu.addSeparator()
        
        # Platform Submenu
        self.platform_menu = self.menu.addMenu(tr("tray.platform", "Platform"))
        
        self.action_ts3 = self.platform_menu.addAction(tr("tray.platform_ts3", "TeamSpeak 3"))
        self.action_ts3.setCheckable(True)
        self.action_ts3.triggered.connect(lambda: self._on_platform_clicked("ts3"))
        
        self.action_mumble = self.platform_menu.addAction(tr("tray.platform_mumble", "Mumble"))
        self.action_mumble.setCheckable(True)
        self.action_mumble.triggered.connect(lambda: self._on_platform_clicked("mumble"))
        
        self.discord_menu = self.platform_menu.addMenu(tr("tray.platform_discord", "Discord"))
        self.action_discord = self.discord_menu.addAction(tr("tray.discord_use", "Use Discord"))
        self.action_discord.setCheckable(True)
        self.action_discord.triggered.connect(lambda: self._on_platform_clicked("discord"))
        self.action_discord_reauth = self.discord_menu.addAction(tr("tray.discord_reauth", "Re-authorize"))
        self.action_discord_reauth.triggered.connect(self.discord_reauthorize_requested.emit)

        self.set_active_platform(initial_platform)
        
        self.settings_action = self.menu.addAction(tr("tray.settings", "Settings"))
        self.settings_action.triggered.connect(self.settings_requested.emit)
        
        self.menu.addSeparator()
        
        self.quit_action = self.menu.addAction(tr("tray.quit", "Quit"))
        self.quit_action.triggered.connect(self.quit_requested.emit)
        
        self.setContextMenu(self.menu)

    def _on_platform_clicked(self, platform):
        self.set_active_platform(platform)
        self.platform_changed.emit(platform)

    def update_overlay_state(self, overlay_id, is_enabled):
        if overlay_id in self.overlay_actions:
            self.overlay_actions[overlay_id].blockSignals(True)
            self.overlay_actions[overlay_id].setChecked(is_enabled)
            self.overlay_actions[overlay_id].blockSignals(False)

    def set_active_platform(self, platform):
        if hasattr(self, 'action_ts3'):
            self.action_ts3.blockSignals(True)
            self.action_mumble.blockSignals(True)
            self.action_discord.blockSignals(True)
            self.action_ts3.setChecked(platform not in ("mumble", "discord"))
            self.action_mumble.setChecked(platform == "mumble")
            self.action_discord.setChecked(platform == "discord")
            self.action_ts3.blockSignals(False)
            self.action_mumble.blockSignals(False)
            self.action_discord.blockSignals(False)

    def set_discord_auth_status(self, authorized: bool, is_active_platform: bool = False):
        if hasattr(self, 'discord_menu') and hasattr(self, 'action_discord_reauth'):
            if is_active_platform and not authorized:
                self.discord_menu.setTitle(tr("tray.platform_discord_warn", "Discord (!)"))
                self.action_discord_reauth.setText(tr("tray.discord_reauth_required", "Re-authorize (Required)"))
                self.setToolTip(tr("tray.tooltip_discord_unauth", "KOverlay v1.2.5 — Discord: Not authorized"))
            else:
                self.discord_menu.setTitle(tr("tray.platform_discord", "Discord"))
                self.action_discord_reauth.setText(tr("tray.discord_reauth", "Re-authorize"))
                self.setToolTip(tr("tray.tooltip_default", "KOverlay v1.2.5"))

    def retranslate_ui(self):
        self.move_action.setText(tr("tray.move_overlays", "Move Overlays"))
        self.mute_action.setText(tr("tray.mute_tts", "Mute TTS Voice"))
        for o_id, action in self.overlay_actions.items():
            action.setText(tr("tray.show_overlay", "Show Overlay {id}", id=o_id))
        self.platform_menu.setTitle(tr("tray.platform", "Platform"))
        self.action_ts3.setText(tr("tray.platform_ts3", "TeamSpeak 3"))
        self.action_mumble.setText(tr("tray.platform_mumble", "Mumble"))
        self.action_discord.setText(tr("tray.discord_use", "Use Discord"))
        self.settings_action.setText(tr("tray.settings", "Settings"))
        self.quit_action.setText(tr("tray.quit", "Quit"))

