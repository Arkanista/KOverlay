import html
import json
import os
import re
import sys

BUILTIN_LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

if sys.platform == "win32":
    _app_data = os.getenv("APPDATA") or os.path.expanduser("~")
    USER_LOCALES_DIR = os.path.join(_app_data, "koverlay", "locales")
else:
    _xdg_config = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    USER_LOCALES_DIR = os.path.join(_xdg_config, "koverlay", "locales")

BUILTIN_LANGUAGE_NAMES = {
    "en": "English",
    "pl": "Polski",
    "de": "Deutsch",
    "ru": "Русский",
    "uk": "Українська",
    "es": "Español",
}

_VALID_LANG_RE = re.compile(r"^[a-zA-Z0-9_-]{2,16}$")
_SAFE_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_DANGEROUS_HTML_RE = re.compile(r"<\s*/?\s*script\b|javascript\s*:|on[a-z]+\s*=", re.IGNORECASE)
_MAX_LOCALE_BYTES = 512 * 1024

_current_lang = "en"
_base_strings = {}
_active_strings = {}


def _sanitize_value(val: str) -> str:
    """Strips potential script/event-handler injections from user-edited locale strings."""
    return _DANGEROUS_HTML_RE.sub("", val)


def _load_json_locale(path: str) -> dict:
    """Safely loads and validates a JSON locale file (pure data only, size-capped)."""
    if not os.path.isfile(path):
        return {}
    try:
        if os.path.getsize(path) > _MAX_LOCALE_BYTES:
            print(f"[KOverlay i18n] Skipping oversized locale file: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        cleaned = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                cleaned[k] = _sanitize_value(v)
        return cleaned
    except Exception as e:
        print(f"[KOverlay i18n] Failed to load locale {path}: {e}")
        return {}


def get_available_languages() -> dict:
    """Returns {lang_code: display_name} from built-in and user-editable locales directories."""
    langs = dict(BUILTIN_LANGUAGE_NAMES)
    for d in (BUILTIN_LOCALES_DIR, USER_LOCALES_DIR):
        if not os.path.isdir(d):
            continue
        try:
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".json"):
                    continue
                code = fname[:-5]
                if not _VALID_LANG_RE.fullmatch(code):
                    continue
                if code not in langs:
                    data = _load_json_locale(os.path.join(d, fname))
                    langs[code] = data.get("_language_name", code.upper())
        except Exception:
            pass
    return langs


def _load_user_overrides(lang_code: str) -> dict:
    """
    Loads user-edited overrides for lang_code.
    If a .snapshots/<lang>.json baseline exists, only keys that actually differ
    from that baseline are treated as overrides—so package updates to unedited
    built-in strings always take effect immediately.
    """
    user_path = os.path.join(USER_LOCALES_DIR, f"{lang_code}.json")
    user_data = _load_json_locale(user_path)
    if not user_data:
        return {}
    snap_path = os.path.join(USER_LOCALES_DIR, ".snapshots", f"{lang_code}.json")
    snap_data = _load_json_locale(snap_path)
    if not snap_data:
        return user_data
    return {k: v for k, v in user_data.items() if snap_data.get(k) != v}


def set_language(lang_code: str):
    """Loads the specified language (merging built-in + user override) with English fallback."""
    global _current_lang, _base_strings, _active_strings

    if not isinstance(lang_code, str) or not _VALID_LANG_RE.fullmatch(lang_code):
        lang_code = "en"

    _base_strings = _load_json_locale(os.path.join(BUILTIN_LOCALES_DIR, "en.json"))
    user_en = _load_user_overrides("en")
    if user_en:
        _base_strings.update(user_en)

    if lang_code == "en":
        _active_strings = dict(_base_strings)
    else:
        loaded = _load_json_locale(os.path.join(BUILTIN_LOCALES_DIR, f"{lang_code}.json"))
        user_override = _load_user_overrides(lang_code)
        loaded.update(user_override)
        _active_strings = loaded

    _current_lang = lang_code


def get_language() -> str:
    return _current_lang


def ensure_user_locales_populated():
    """
    Copies built-in locale JSONs into USER_LOCALES_DIR for user editing,
    and updates any unedited files when a newer package version is installed.
    """
    import shutil
    snap_dir = os.path.join(USER_LOCALES_DIR, ".snapshots")
    os.makedirs(USER_LOCALES_DIR, exist_ok=True)
    os.makedirs(snap_dir, exist_ok=True)
    if not os.path.isdir(BUILTIN_LOCALES_DIR):
        return
    for fname in os.listdir(BUILTIN_LOCALES_DIR):
        if fname.endswith(".json") and _VALID_LANG_RE.fullmatch(fname[:-5]):
            src = os.path.join(BUILTIN_LOCALES_DIR, fname)
            dst = os.path.join(USER_LOCALES_DIR, fname)
            snap = os.path.join(snap_dir, fname)
            if not os.path.isfile(src):
                continue
            try:
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    shutil.copy2(src, snap)
                elif os.path.isfile(snap):
                    # Refresh unedited user copy when built-in locale changed after package upgrade
                    cur_user = _load_json_locale(dst)
                    cur_snap = _load_json_locale(snap)
                    if cur_user == cur_snap and cur_snap != _load_json_locale(src):
                        shutil.copy2(src, dst)
                        shutil.copy2(src, snap)
            except Exception:
                pass


def _safe_format(template: str, kwargs: dict) -> str:
    """
    Substitutes simple {key} placeholders without ever calling str.format(),
    preventing format-string attribute/code injection from user-edited JSON files.
    """
    if not kwargs:
        return template

    def _replace(match):
        key = match.group(1)
        if key in kwargs:
            val = kwargs[key]
            return html.escape(str(val)) if "<" in template and ">" in template else str(val)
        return match.group(0)

    return _SAFE_PLACEHOLDER_RE.sub(_replace, template)


def tr(key: str, default: str = None, **kwargs) -> str:
    """Translates key using active language, falling back to English, then default/key."""
    if not _base_strings:
        set_language(_current_lang)
    text = _active_strings.get(key)
    if text is None:
        text = _base_strings.get(key)
    if text is None:
        text = default if default is not None else key
    return _safe_format(text, kwargs)
