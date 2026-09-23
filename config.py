import json
import os

CONFIG_FILE = os.path.expanduser("~/.config/ts3-overlay/config.json")

def load_config():
    default_config = {
        "voice_backend": "ts3",
        "api_key": "",
        "mumble_port": 25640,
        "opacity": 0.8,
        "recent_speakers_first": False,
        "speaker_fade_duration": 5,
        "limit_users_enabled": False,
        "limit_users_count": "10",
        "strip_bracket_tags": False,
        "nickname_prefixes": []
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
            if "recent_speakers_first" not in cfg:
                cfg["recent_speakers_first"] = False
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
