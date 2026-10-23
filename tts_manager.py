import os
import sys
import glob
import tempfile
import hashlib
import shutil
import subprocess
import threading
import queue
import time
import importlib
import importlib.util
import re

def find_executable(name):
    """Finds an executable in PATH or common Linux/Homebrew/KOverlay directories."""
    found = shutil.which(name)
    if found:
        return found
    app_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_dirs = [
        app_dir,
        os.path.join(app_dir, "bin"),
        os.path.expanduser("~/.local/share/koverlay/venv/bin"),
        os.path.expanduser("~/.local/share/koverlay/bin"),
        os.path.expanduser("~/.local/bin"),
        "/opt/koverlay/bin",
        "/opt/koverlay/lib/bin",
        "/home/linuxbrew/.linuxbrew/bin",
        os.path.expanduser("~/.linuxbrew/bin"),
        "/usr/local/bin",
        "/usr/bin",
    ]
    for d in candidate_dirs:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None

def ensure_edge_tts_available():
    """
    Checks if edge_tts Python module or edge-tts CLI is available.
    Dynamically attaches local KOverlay venv/lib site-packages if needed.
    Returns (has_module: bool, cli_path: str | None).
    """
    has_module = importlib.util.find_spec("edge_tts") is not None
    if not has_module and sys.platform != "win32":
        app_dir = os.path.dirname(os.path.abspath(__file__))
        extra_site_dirs = (
            glob.glob(os.path.join(app_dir, "venv", "lib", "python*", "site-packages"))
            + glob.glob(os.path.expanduser("~/.local/share/koverlay/venv/lib/python*/site-packages"))
            + ["/opt/koverlay/lib"]
            + glob.glob(os.path.expanduser("~/.local/lib/python*/site-packages"))
        )
        added = False
        for sp in extra_site_dirs:
            if os.path.isdir(os.path.join(sp, "edge_tts")) and sp not in sys.path:
                sys.path.insert(0, sp)
                added = True
        if added:
            importlib.invalidate_caches()
            try:
                has_module = importlib.util.find_spec("edge_tts") is not None
            except Exception:
                has_module = False

    cli_name = "edge-tts.exe" if sys.platform == "win32" else "edge-tts"
    cli_path = find_executable(cli_name)
    return has_module, cli_path

def find_available_audio_players():
    """
    Returns a list of all detected audio players as (player_type, player_bin) tuples,
    ordered from most recommended to fallback.
    """
    players = []
    mpv_name = "mpv.exe" if sys.platform == "win32" else "mpv"
    mpv_bin = find_executable(mpv_name)
    if mpv_bin:
        players.append(("mpv", mpv_bin))

    if sys.platform == "win32":
        players.append(("win32_mci", "winmm"))
        return players

    for player in ("ffplay", "pw-play", "paplay", "gst-play-1.0", "cvlc"):
        bin_path = find_executable(player)
        if bin_path:
            players.append((player, bin_path))

    return players

def find_audio_player(preferred=None):
    """
    Finds the best available audio player capable of playing MP3 files,
    or the user's preferred player if specified and available.
    Returns (player_type: str | None, player_bin: str | None).
    """
    available = find_available_audio_players()
    if not available:
        return None, None

    if preferred and preferred != "auto":
        for p_type, p_bin in available:
            if p_type == preferred:
                return p_type, p_bin

    return available[0]

def check_tts_status(preferred_player=None):
    """Returns a dictionary with detailed TTS availability and backend info."""
    has_module, cli_path = ensure_edge_tts_available()
    edge_tts_ok = has_module or (cli_path is not None)
    available_players = find_available_audio_players()
    player_type, player_bin = find_audio_player(preferred_player)
    player_ok = player_type is not None
    return {
        "available": edge_tts_ok and player_ok,
        "edge_tts": edge_tts_ok,
        "has_module": has_module,
        "edge_tts_cli": cli_path,
        "player_type": player_type,
        "player_bin": player_bin,
        "available_players": available_players,
    }

def apply_tts_aliases(name, aliases):
    if not aliases:
        return name
    spoken_name = name
    for src, dst in aliases.items():
        if src:
            # Case insensitive substring replacement
            spoken_name = re.sub(re.escape(src), dst, spoken_name, flags=re.IGNORECASE)
    return spoken_name

class TTSManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config=None, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TTSManager, cls).__new__(cls)
                cls._instance._init_once(config)
            elif config is not None:
                cls._instance.config = config
            return cls._instance

    def _init_once(self, config):
        if config is None:
            config = {}
        self.config = config
            
        self.message_queue = queue.Queue(maxsize=5)
        self.is_running = True
        self.refresh_capabilities()
        
        # Setup persistent cache directory
        if sys.platform == "win32":
            base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
            self.cache_dir = os.path.join(base_dir, "koverlay", "tts_cache")
        else:
            self.cache_dir = os.path.expanduser("~/.cache/koverlay/tts_cache")
            legacy_cache_dir = os.path.expanduser("~/.cache/ts3-overlay/tts_cache")
            if not os.path.exists(self.cache_dir) and os.path.exists(legacy_cache_dir):
                try:
                    os.makedirs(os.path.dirname(self.cache_dir), exist_ok=True)
                    import shutil
                    shutil.copytree(legacy_cache_dir, self.cache_dir)
                except Exception:
                    pass
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Cleanup old files
        retention_days = config.get("tts_cache_retention_days", 30)
        self._cleanup_old_cache(retention_days)
        
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def refresh_capabilities(self, preferred_player=None):
        if preferred_player is None and isinstance(getattr(self, "config", None), dict):
            preferred_player = self.config.get("tts_audio_player", "auto")
        status = check_tts_status(preferred_player)
        self.edge_tts_installed = status["edge_tts"]
        self.has_edge_tts_module = status["has_module"]
        self.edge_tts_cli = status["edge_tts_cli"]
        return status

    def _cleanup_old_cache(self, retention_days):
        if retention_days <= 0:
            return
            
        now = time.time()
        retention_seconds = retention_days * 24 * 60 * 60
        
        try:
            for filename in os.listdir(self.cache_dir):
                if not filename.endswith(".mp3"):
                    continue
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    if now - mtime > retention_seconds:
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass
        except Exception as e:
            print(f"Failed to cleanup TTS cache: {e}")

    def get_cache_size(self):
        """Returns cache size in megabytes."""
        total_size = 0
        try:
            for dirpath, _, filenames in os.walk(self.cache_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except Exception:
            pass
        return total_size / (1024 * 1024)

    def clear_cache(self):
        """Deletes all files in the cache directory."""
        try:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
            return True
        except Exception as e:
            print(f"Failed to clear cache: {e}")
            return False

    def enqueue(self, text, voice="en-US-AriaNeural", volume=80, delay=0, rate="+0%"):
        """Add a TTS message to the queue to be played sequentially."""
        if not text:
            return
        try:
            self.message_queue.put({
                "text": text,
                "voice": voice,
                "volume": volume,
                "delay": delay,
                "rate": rate
            }, block=False)
        except queue.Full:
            print("TTS Queue is full. Dropping message:", text)

    def clear_queue(self):
        """Clears all pending announcements from the queue."""
        try:
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
                except Exception:
                    break
        except Exception:
            pass

    def stop(self):
        """Signal the worker thread to stop processing."""
        self.is_running = False
        # Push a dummy item to unblock the queue if it's waiting
        try:
            self.message_queue.put(None, block=False)
        except queue.Full:
            pass

    def _process_queue(self):
        while self.is_running:
            try:
                was_empty = self.message_queue.empty()
                item = self.message_queue.get()
                if item is None: # Stop signal
                    break

                # Apply delay only if it's the first message after being idle
                # If there's a backlog, we don't want the delays to stack up.
                if item["delay"] > 0 and was_empty:
                    time.sleep(item["delay"])

                self._play_sync(item)
                self.message_queue.task_done()
            except Exception as e:
                print(f"Error in TTS worker thread: {e}")

    def _play_win32_mci(self, filepath, volume=80):
        try:
            import ctypes
            import uuid
            alias = f"tts_{uuid.uuid4().hex[:8]}"
            winmm = ctypes.windll.winmm
            res = winmm.mciSendStringW(f'open "{filepath}" type mpegvideo alias {alias}', None, 0, None)
            if res != 0:
                return False
            try:
                vol_val = max(0, min(1000, int(volume * 10)))
                winmm.mciSendStringW(f'setaudio {alias} volume to {vol_val}', None, 0, None)
                winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
            finally:
                winmm.mciSendStringW(f'close {alias}', None, 0, None)
            return True
        except Exception as e:
            print(f"Windows MCI playback error: {e}")
            return False

    def _play_mp3_file(self, filepath, player_type, player_bin, vol):
        c_env = {**os.environ, "LC_NUMERIC": "C"}
        if player_type == "mpv":
            subprocess.run([
                player_bin,
                "--no-video",
                "--no-terminal",
                f"--volume={vol}",
                "--af=silenceremove=stop_periods=-1:stop_duration=0:stop_threshold=-70dB",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        elif player_type == "ffplay":
            subprocess.run([
                player_bin,
                "-nodisp",
                "-autoexit",
                "-loglevel", "quiet",
                "-volume", str(max(0, min(100, int(vol)))),
                "-af", "silenceremove=stop_periods=-1:stop_duration=0:stop_threshold=-70dB",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        elif player_type == "pw-play":
            vol_float = max(0.0, min(1.0, float(vol) / 100.0))
            subprocess.run([
                player_bin,
                f"--volume={vol_float:.2f}",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        elif player_type == "paplay":
            vol_pa = max(0, min(65536, int((float(vol) / 100.0) * 65536)))
            subprocess.run([
                player_bin,
                f"--volume={vol_pa}",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        elif player_type == "gst-play-1.0":
            vol_float = max(0.0, min(1.0, float(vol) / 100.0))
            subprocess.run([
                player_bin,
                "--no-interactive",
                "--quiet",
                f"--volume={vol_float:.2f}",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        elif player_type == "cvlc":
            vol_float = max(0.0, min(2.0, float(vol) / 100.0))
            subprocess.run([
                player_bin,
                "--play-and-exit",
                "--no-video",
                "--quiet",
                f"--gain={vol_float:.2f}",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        elif player_type == "win32_mci":
            self._play_win32_mci(filepath, vol)

    def _play_sync(self, item):
        text = item["text"]
        voice = item["voice"]
        vol = item["volume"]
        rate = item["rate"]
        safe_text = "".join(c for c in text if c.isalnum() or c in " _-.")

        if not self.edge_tts_installed:
            self.refresh_capabilities()

        preferred = self.config.get("tts_audio_player", "auto") if isinstance(getattr(self, "config", None), dict) else "auto"
        player_type, player_bin = find_audio_player(preferred)
        can_play_mp3 = player_type is not None

        if self.edge_tts_installed and can_play_mp3:
            try:
                # Cache the generated voice per text, voice and rate
                cache_key = safe_text + "_" + voice + "_" + rate
                # Create a human-readable filename instead of MD5 hash
                safe_filename = "".join(c for c in cache_key if c.isalnum() or c in "_-+.%").replace(" ", "_")
                # Limit length just in case
                if len(safe_filename) > 150:
                    safe_filename = safe_filename[:100] + "_" + hashlib.md5(cache_key.encode()).hexdigest()[:8]
                tmp_file = os.path.join(self.cache_dir, f"{safe_filename}.mp3")
                
                if not os.path.exists(tmp_file):
                    if getattr(self, "has_edge_tts_module", False) or importlib.util.find_spec("edge_tts") is not None:
                        import edge_tts
                        import asyncio
                        communicate = edge_tts.Communicate(text, voice, rate=rate)
                        asyncio.run(communicate.save(tmp_file))
                    elif getattr(self, "edge_tts_cli", None):
                        subprocess.run([
                            self.edge_tts_cli,
                            "--text", text,
                            "--voice", voice,
                            f"--rate={rate}",
                            "--write-media", tmp_file
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    
                if os.path.exists(tmp_file):
                    self._play_mp3_file(tmp_file, player_type, player_bin, vol)
            except Exception as e:
                print(f"Edge TTS error: {e}")
                
        elif shutil.which("espeak"):
            lang = voice.split("-")[0]
            vol_val = int(vol * 2)
            speed = 175
            if rate == "+25%": speed = 220
            elif rate == "+50%": speed = 260
            elif rate == "-25%": speed = 130
            subprocess.run(
                ["espeak", "-a", str(vol_val), "-s", str(speed), "-v", lang, text],
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
        elif shutil.which("spd-say"):
            # Note: spd-say operates asynchronously via speech-dispatcher. 
            # To make it synchronous, we use -w (wait) flag.
            lang = voice.split("-")[0]
            vol_val = int((vol - 50) * 2)
            speed = 0
            if rate == "+25%": speed = 25
            elif rate == "+50%": speed = 50
            elif rate == "-25%": speed = -25
            subprocess.run(
                ["spd-say", "-w", "-y", str(vol_val), "-r", str(speed), "-l", lang, text],
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
        elif sys.platform == "win32":
            # Native Windows SAPI fallback via PowerShell
            try:
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$synth.Volume = {vol}; "
                    f"$synth.Speak('{text}')"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

# Global accessor
def get_tts_manager(config=None):
    """Returns the singleton instance of TTSManager."""
    return TTSManager(config)
