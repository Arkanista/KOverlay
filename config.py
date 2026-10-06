import json
import os
import sys

if sys.platform == "win32":
    app_data = os.getenv("APPDATA") or os.path.expanduser("~")
    CONFIG_DIR = os.path.join(app_data, "koverlay")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
    LEGACY_CONFIG_FILE = None
    DOT_CONFIG_DIR = None
else:
    xdg_config = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    CONFIG_DIR = os.path.join(xdg_config, "koverlay")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
    LEGACY_CONFIG_DIR = os.path.expanduser("~/.config/ts3-overlay")
    LEGACY_CONFIG_FILE = os.path.join(LEGACY_CONFIG_DIR, "config.json")

def _migrate_legacy_config():
    if sys.platform == "win32":
        return
    try:
        # Migrate config file if new one does not exist but legacy one does
        if not os.path.exists(CONFIG_FILE):
            if LEGACY_CONFIG_FILE and os.path.exists(LEGACY_CONFIG_FILE):
                os.makedirs(CONFIG_DIR, exist_ok=True)
                import shutil
                shutil.copy2(LEGACY_CONFIG_FILE, CONFIG_FILE)
                print(f"[KOverlay] Migrated configuration from {LEGACY_CONFIG_FILE} to {CONFIG_FILE}")
            elif os.path.exists(os.path.expanduser("~/.koverlay/config.json")) and not os.path.islink(os.path.expanduser("~/.koverlay")):
                os.makedirs(CONFIG_DIR, exist_ok=True)
                import shutil
                shutil.copy2(os.path.expanduser("~/.koverlay/config.json"), CONFIG_FILE)

        # Remove any lingering ~/.koverlay symlink if present
        dot_symlink = os.path.expanduser("~/.koverlay")
        if os.path.islink(dot_symlink):
            try:
                os.unlink(dot_symlink)
            except Exception:
                pass
    except Exception as e:
        print(f"[KOverlay] Note during config migration: {e}")

def load_config():
    _migrate_legacy_config()
    default_config = {
        "voice_backend": "ts3",
        "api_key": "",
        "mumble_port": 25640,
        "discord_client_id": "207646673902501888",
        "discord_access_token": "",
        "opacity": 0.8,
        "sort_order": "alphabetical_fading_top",
        "recent_speakers_first": False,
        "speaker_fade_duration": 5,
        "limit_users_enabled": False,
        "limit_users_count": "10",
        "strip_bracket_tags": False,
        "nickname_prefixes": [],
        "line_height": 0
    }
    if not os.path.exists(CONFIG_FILE):
        return default_config
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            # Ensure defaults for newly introduced keys
            if "voice_backend" not in cfg:
                cfg["voice_backend"] = "ts3"
            if "mumble_port" not in cfg:
                cfg["mumble_port"] = 25640
            if "discord_client_id" not in cfg:
                cfg["discord_client_id"] = "207646673902501888"
            if "discord_access_token" not in cfg:
                cfg["discord_access_token"] = ""
            if "sort_order" not in cfg or cfg.get("sort_order") == "voice":
                if cfg.get("recent_speakers_first", False) and cfg.get("sort_order") != "voice":
                    cfg["sort_order"] = "recent_speakers"
                else:
                    cfg["sort_order"] = "alphabetical_fading_top"
            if "recent_speakers_first" not in cfg:
                cfg["recent_speakers_first"] = (cfg.get("sort_order") == "recent_speakers")
            if "speaker_fade_duration" not in cfg:
                cfg["speaker_fade_duration"] = 5
            if "limit_users_enabled" not in cfg:
                cfg["limit_users_enabled"] = False
            if "limit_users_count" not in cfg:
                cfg["limit_users_count"] = "10"
            if "strip_bracket_tags" not in cfg:
                cfg["strip_bracket_tags"] = False
            if "nickname_prefixes" not in cfg:
                cfg["nickname_prefixes"] = []
            if "line_height" not in cfg:
                cfg["line_height"] = 0
            return cfg
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

import re

def clean_nickname(name: str, config: dict) -> str:
    """
    Cleans tags and prefixes from a nickname according to configuration:
    - strip_bracket_tags: strips leading tags in [...], (...), {...}
    - nickname_prefixes: list of custom prefix strings to strip from the beginning
      (if "[]", "()", or "{}" is included in the list, it acts as bracket stripping)
    """
    if not name:
        return name
        
    strip_brackets = config.get("strip_bracket_tags", False)
    prefixes = config.get("nickname_prefixes", [])
    
    strip_square = strip_brackets or any(p.strip() in ("[]", "[...]", "[*]") for p in prefixes)
    strip_round = strip_brackets or any(p.strip() in ("()", "(...)", "(*)") for p in prefixes)
    strip_curly = strip_brackets or any(p.strip() in ("{}", "{...}", "{*}") for p in prefixes)

    cleaned = name
    for _ in range(5):
        prev = cleaned
        if strip_square:
            cleaned = re.sub(r'^\s*\[[^\]]*\]\s*', '', cleaned)
        if strip_round:
            cleaned = re.sub(r'^\s*\([^\)]*\)\s*', '', cleaned)
        if strip_curly:
            cleaned = re.sub(r'^\s*\{[^\}]*\}\s*', '', cleaned)
            
        for p in prefixes:
            p_strip = p.strip()
            if not p_strip or p_strip in ("[]", "[...]", "[*]", "()", "(...)", "(*)", "{}", "{...}", "{*}"):
                continue
            if cleaned.lower().startswith(p_strip.lower()):
                cleaned = cleaned[len(p_strip):].lstrip()

        if cleaned == prev:
            break

    cleaned = cleaned.strip()
    return cleaned if cleaned else name

def save_config(config_data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")
