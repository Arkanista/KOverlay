#!/usr/bin/env python3
"""
Parallel Google Translate (keyless) translator for KOverlay locale files.
Translates locales/en.json into Polish, German, Russian, Ukrainian, and Spanish
simultaneously using ThreadPoolExecutor and the public Google Translate endpoint.

Usage:
    python3 scripts/translate_locales.py
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import urllib.parse
import urllib.request

TARGET_LANGUAGES = {
    "pl": ("Polish", "Polski"),
    "de": ("German", "Deutsch"),
    "ru": ("Russian", "Русский"),
    "uk": ("Ukrainian", "Українська"),
    "es": ("Spanish", "Español"),
}

_DANGEROUS_HTML_RE = re.compile(r"<\s*/?\s*script\b|javascript\s*:|on[a-z]+\s*=", re.IGNORECASE)
_PROTECT_RE = re.compile(
    r"(\{[a-zA-Z0-9_]+\}|%NICK|</?(?:b|i|br|code|h3|hr)\s*/?>|&(?:bull|mdash|amp);|TeamSpeak 3|TeamSpeak|TS3|Mumble|Discord|KOverlay|ClientQuery|TTS|IPC|mpv|ffplay|pw-play|paplay|gst-play-1\.0|cvlc|silenceremove|pipewire-pulse|PipeWire|PulseAudio|GStreamer|VLC|Bazzite|SteamOS|Fedora Silverblue/Kinoite|Homebrew|brew install mpv)"
)


def _protect_tokens(text: str) -> tuple[str, list[str]]:
    tokens = []

    def _repl(match):
        idx = len(tokens)
        tokens.append(match.group(0))
        return f" 8810{idx:03d} "

    return _PROTECT_RE.sub(_repl, text), tokens


def _restore_tokens(text: str, tokens: list[str]) -> str:
    for idx, tok in enumerate(tokens):
        text = re.sub(rf"\s*8810{idx:03d}\s*", lambda _m, t=tok: f" {t} " if not t.startswith("<") else t, text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\s+([.,!?;:)])", r"\1", text)
    text = re.sub(r"([¡¿(])\s+", r"\1", text)
    text = re.sub(r"<br>\s+", "<br>", text)
    return text.strip()


def _google_translate_batch(texts: list[str], target_lang: str, source_lang: str = "en") -> list[str]:
    """Translates a batch of strings in a single HTTP request to avoid rate limits."""
    protected_list = []
    tokens_list = []
    for t in texts:
        p, toks = _protect_tokens(t)
        protected_list.append(p)
        tokens_list.append(toks)

    sep = "\n99887766\n"
    joined = sep.join(protected_list)
    params = urllib.parse.urlencode({
        "client": "dict-chrome-ex",
        "sl": source_lang,
        "tl": target_lang,
    })
    body = urllib.parse.urlencode({"q": joined}).encode("utf-8")
    url = f"https://clients5.google.com/translate_a/t?{params}"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, list) and data and isinstance(data[0], str):
        translated_joined = data[0]
    elif isinstance(data, list) and data and isinstance(data[0], list):
        translated_joined = "".join(str(part[0]) for part in data if part and part[0])
    elif isinstance(data, dict) and "sentences" in data:
        translated_joined = "".join(s.get("trans", "") for s in data["sentences"])
    else:
        translated_joined = "".join(part[0] for part in data[0] if part and part[0])
    parts = re.split(r"\s*99887766\s*", translated_joined)
    if len(parts) != len(texts):
        raise ValueError(f"Batch split mismatch: expected {len(texts)}, got {len(parts)}")
    return [_restore_tokens(part.strip(), toks) for part, toks in zip(parts, tokens_list)]


def translate_language(source_data: dict, lang_code: str, native_name: str, out_dir: str) -> tuple[str, bool, str]:
    try:
        keys_to_translate = []
        vals_to_translate = []
        sanitized = {}

        for key, en_val in source_data.items():
            if key == "_language_name":
                sanitized[key] = native_name
            elif not isinstance(en_val, str) or not en_val.strip():
                sanitized[key] = str(en_val)
            else:
                keys_to_translate.append(key)
                vals_to_translate.append(en_val)

        # Split into chunks of <= 25 items (~1-2 requests per language)
        chunk_size = 25
        for i in range(0, len(keys_to_translate), chunk_size):
            k_chunk = keys_to_translate[i:i + chunk_size]
            v_chunk = vals_to_translate[i:i + chunk_size]
            t_chunk = _google_translate_batch(v_chunk, lang_code)
            for k, t_val in zip(k_chunk, t_chunk):
                sanitized[k] = _DANGEROUS_HTML_RE.sub("", t_val)

        # Preserve original key ordering from en.json
        ordered = {k: sanitized[k] for k in source_data.keys() if k in sanitized}
        out_path = os.path.join(out_dir, f"{lang_code}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ordered, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return lang_code, True, out_path
    except Exception as e:
        return lang_code, False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Translate KOverlay locales in parallel via Google Translate (no API key).")
    parser.add_argument("--locales-dir", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales"))
    args = parser.parse_args()

    en_path = os.path.join(args.locales_dir, "en.json")
    with open(en_path, "r", encoding="utf-8") as f:
        source_data = json.load(f)

    print(f"Translating {len(source_data)} strings into {len(TARGET_LANGUAGES)} languages concurrently...")

    failed = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TARGET_LANGUAGES)) as executor:
        futures = [
            executor.submit(translate_language, source_data, code, native_name, args.locales_dir)
            for code, (_eng_name, native_name) in TARGET_LANGUAGES.items()
        ]
        for fut in concurrent.futures.as_completed(futures):
            code, ok, info = fut.result()
            if ok:
                print(f"  [OK] {code} -> {info}")
            else:
                print(f"  [FAIL] {code}: {info}", file=sys.stderr)
                failed = True

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
