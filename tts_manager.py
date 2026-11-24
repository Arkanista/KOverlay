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


def supports_live_ducking(player_type: str | None) -> bool:
    """Returns True if the given audio player supports live volume ducking on this OS."""
    if not player_type:
        return False
    if sys.platform == "win32":
        return player_type == "win32_mci"
    if player_type == "mpv":
        return True
    if player_type in ("ffplay", "pw-play", "paplay", "gst-play-1.0", "cvlc"):
        return shutil.which("pactl") is not None
    return False

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

DEFAULT_DIGIT_REPLACEMENTS = {
    "0": "o",
    "1": "i",
    "2": "z",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "b",
    "7": "t",
    "8": "b",
    "9": "g"
}

def apply_digit_replacements(name: str, digit_map: dict) -> str:
    if not name or not digit_map or not isinstance(name, str):
        return str(name) if name is not None else ""
    result = []
    for ch in name:
        rep = digit_map.get(ch)
        if rep is not None and rep != "":
            result.append(rep)
        else:
            result.append(ch)
    return "".join(result)

def apply_tts_aliases(name, aliases):
    if not aliases:
        return name
    spoken_name = name
    for src, dst in aliases.items():
        if src:
            # Case insensitive substring replacement
            spoken_name = re.sub(re.escape(src), dst, spoken_name, flags=re.IGNORECASE)
    return spoken_name

def prepare_tts_nickname(name: str, config: dict = None) -> str:
    """
    Prepares a nickname for TTS announcement:
    1. Strips prefixes/tags (clean_nickname)
    2. Replaces digits with letters (if tts_replace_digits is enabled)
    3. Converts uppercase letters to lowercase (if tts_lowercase is enabled)
    4. Applies TTS aliases (apply_tts_aliases)
    """
    if not name:
        return ""
    if config is None:
        config = {}

    from config import clean_nickname
    spoken = clean_nickname(name, config)

    # Step 1: Digit to letter replacement (executed before aliases)
    if config.get("tts_replace_digits", True):
        digit_map = config.get("tts_digit_replacements", DEFAULT_DIGIT_REPLACEMENTS)
        spoken = apply_digit_replacements(spoken, digit_map)

    # Step 2: Uppercase to lowercase conversion (executed before aliases)
    if config.get("tts_lowercase", True):
        spoken = spoken.lower()

    # Step 3: Custom aliases substitution
    aliases = config.get("tts_aliases", {})
    spoken = apply_tts_aliases(spoken, aliases)
    return spoken

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

    def _get_target_volume(self, base_vol):
        """Returns effective TTS volume, ducked if someone is actively speaking."""
        try:
            from audio_ducking import get_voip_audio_monitor
            monitor = get_voip_audio_monitor(self.config)
            if monitor.should_duck():
                duck_pct = max(0, min(100, int(self.config.get("tts_duck_volume_pct", 25))))
                return max(0, min(100, int(round(base_vol * (duck_pct / 100.0)))))
        except Exception:
            pass
        return max(0, min(100, int(base_vol)))

    def _play_win32_mci(self, filepath, volume=80):
        ole32 = None
        com_initialized = False
        try:
            import ctypes
            import uuid

            # DirectShow / Quartz MCI filters use COM on worker threads
            try:
                ole32 = ctypes.windll.ole32
                hr = ole32.CoInitialize(None)
                com_initialized = hr in (0, 1)
            except Exception:
                pass

            # Prefer 8.3 short path to avoid MCI issues with '%', spaces, or long paths
            mci_path = filepath
            try:
                buf = ctypes.create_unicode_buffer(512)
                if ctypes.windll.kernel32.GetShortPathNameW(filepath, buf, 512) > 0:
                    mci_path = buf.value
            except Exception:
                pass

            alias = f"tts_{uuid.uuid4().hex[:8]}"
            winmm = ctypes.windll.winmm
            res = winmm.mciSendStringW(f'open "{mci_path}" type mpegvideo alias {alias}', None, 0, None)
            if res != 0:
                err_buf = ctypes.create_unicode_buffer(256)
                winmm.mciGetErrorStringW(res, err_buf, 256)
                print(f"Windows MCI open error ({res}): {err_buf.value}")
                return False
            try:
                cur_vol = self._get_target_volume(volume)
                vol_val = max(0, min(1000, int(cur_vol * 10)))
                winmm.mciSendStringW(f'setaudio {alias} volume to {vol_val}', None, 0, None)
                play_res = winmm.mciSendStringW(f'play {alias}', None, 0, None)
                if play_res != 0:
                    err_buf = ctypes.create_unicode_buffer(256)
                    winmm.mciGetErrorStringW(play_res, err_buf, 256)
                    print(f"Windows MCI play error ({play_res}): {err_buf.value}")
                    return False

                status_buf = ctypes.create_unicode_buffer(64)
                while self.is_running:
                    time.sleep(0.02)
                    if winmm.mciSendStringW(f'status {alias} mode', status_buf, 64, None) != 0:
                        break
                    if status_buf.value.strip().lower() != "playing":
                        break
                    new_vol = self._get_target_volume(volume)
                    if new_vol != cur_vol:
                        cur_vol = new_vol
                        vol_val = max(0, min(1000, int(cur_vol * 10)))
                        winmm.mciSendStringW(f'setaudio {alias} volume to {vol_val}', None, 0, None)
            finally:
                winmm.mciSendStringW(f'close {alias}', None, 0, None)
            return True
        except Exception as e:
            print(f"Windows MCI playback error: {e}")
            return False
        finally:
            if com_initialized and ole32 is not None:
                try:
                    ole32.CoUninitialize()
                except Exception:
                    pass

    def _play_mpv_live(self, player_bin, filepath, base_vol, c_env):
        """Plays MP3 with mpv and dynamically updates volume via IPC socket."""
        import json
        import socket

        if sys.platform == "win32":
            eff_vol = self._get_target_volume(base_vol)
            subprocess.run([
                player_bin,
                "--no-video",
                "--no-terminal",
                f"--volume={eff_vol}",
                "--af=silenceremove=stop_periods=-1:stop_duration=0:stop_threshold=-70dB",
                filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
            return

        ipc_path = os.path.join(
            tempfile.gettempdir(),
            f"koverlay_mpv_{os.getpid()}_{threading.get_ident()}.sock",
        )
        try:
            if os.path.exists(ipc_path):
                os.unlink(ipc_path)
        except Exception:
            pass

        cur_vol = self._get_target_volume(base_vol)
        proc = subprocess.Popen(
            [
                player_bin,
                "--no-video",
                "--no-terminal",
                f"--volume={cur_vol}",
                f"--input-ipc-server={ipc_path}",
                "--af=silenceremove=stop_periods=-1:stop_duration=0:stop_threshold=-70dB",
                filepath,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=c_env,
        )
        try:
            while proc.poll() is None and self.is_running:
                time.sleep(0.02)
                new_vol = self._get_target_volume(base_vol)
                if new_vol != cur_vol and os.path.exists(ipc_path):
                    try:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                            s.settimeout(0.1)
                            s.connect(ipc_path)
                            cmd = json.dumps({"command": ["set_property", "volume", new_vol]}) + "\n"
                            s.sendall(cmd.encode("utf-8"))
                        cur_vol = new_vol
                    except Exception:
                        pass
        finally:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=0.5)
                except Exception:
                    pass
            try:
                if os.path.exists(ipc_path):
                    os.unlink(ipc_path)
            except Exception:
                pass

    def _play_linux_with_live_ducking(self, cmd, c_env, monitor, player_name=None):
        """
        Launches a Linux audio player (ffplay, pw-play, paplay, etc.) at base volume
        and dynamically ducks its PulseAudio/PipeWire sink-input volume via pactl.
        """
        from audio_ducking import find_sink_input_by_pid, set_sink_input_volume_pct

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
        sink_idx = None
        cur_rel_pct = 100
        last_lookup = 0.0
        try:
            while proc.poll() is None and self.is_running:
                now = time.monotonic()
                if sink_idx is None and (now - last_lookup) >= 0.04:
                    last_lookup = now
                    sink_idx = find_sink_input_by_pid(proc.pid, player_name=player_name)
                    if sink_idx is not None and monitor.should_duck():
                        duck_pct = max(0, min(100, int(self.config.get("tts_duck_volume_pct", 25))))
                        if set_sink_input_volume_pct(sink_idx, duck_pct):
                            cur_rel_pct = duck_pct
                elif sink_idx is not None:
                    duck_pct = max(0, min(100, int(self.config.get("tts_duck_volume_pct", 25))))
                    target_rel = duck_pct if monitor.should_duck() else 100
                    if target_rel != cur_rel_pct:
                        if set_sink_input_volume_pct(sink_idx, target_rel):
                            cur_rel_pct = target_rel
                time.sleep(0.02)
        finally:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=0.5)
                except Exception:
                    pass

    def _play_mp3_file(self, filepath, player_type, player_bin, vol):
        from audio_ducking import get_voip_audio_monitor
        monitor = get_voip_audio_monitor(self.config)
        monitor.set_tts_playing(True)
        try:
            c_env = {**os.environ, "LC_NUMERIC": "C"}
            if player_type == "mpv":
                self._play_mpv_live(player_bin, filepath, vol, c_env)
            elif player_type == "ffplay":
                cmd = [
                    player_bin,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel", "quiet",
                    "-volume", str(max(0, min(100, int(vol)))),
                    "-af", "silenceremove=stop_periods=-1:stop_duration=0:stop_threshold=-70dB",
                    filepath,
                ]
                if sys.platform != "win32":
                    self._play_linux_with_live_ducking(cmd, c_env, monitor, player_name="ffplay")
                else:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=c_env)
            elif player_type == "pw-play":
                vol_float = max(0.0, min(1.0, float(vol) / 100.0))
                self._play_linux_with_live_ducking([player_bin, f"--volume={vol_float:.2f}", filepath], c_env, monitor, player_name="pw-play")
            elif player_type == "paplay":
                vol_pa = max(0, min(65536, int((float(vol) / 100.0) * 65536)))
                self._play_linux_with_live_ducking([player_bin, f"--volume={vol_pa}", filepath], c_env, monitor, player_name="paplay")
            elif player_type == "gst-play-1.0":
                vol_float = max(0.0, min(1.0, float(vol) / 100.0))
                self._play_linux_with_live_ducking(
                    [player_bin, "--no-interactive", "--quiet", f"--volume={vol_float:.2f}", filepath],
                    c_env,
                    monitor,
                    player_name="gst-play-1.0",
                )
            elif player_type == "cvlc":
                vol_float = max(0.0, min(2.0, float(vol) / 100.0))
                self._play_linux_with_live_ducking(
                    [player_bin, "--play-and-exit", "--no-video", "--quiet", f"--gain={vol_float:.2f}", filepath],
                    c_env,
                    monitor,
                    player_name="vlc",
                )
            elif player_type == "win32_mci":
                self._play_win32_mci(filepath, vol)
        finally:
            monitor.set_tts_playing(False)

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
                
                needs_download = (not os.path.exists(tmp_file)) or (os.path.getsize(tmp_file) == 0)
                if needs_download:
                    part_file = f"{tmp_file}.{os.getpid()}.{threading.get_ident()}.part"
                    try:
                        if getattr(self, "has_edge_tts_module", False) or importlib.util.find_spec("edge_tts") is not None:
                            import edge_tts
                            import asyncio

                            async def _fetch_edge_audio():
                                communicate = edge_tts.Communicate(
                                    text,
                                    voice,
                                    rate=rate,
                                    connect_timeout=10,
                                    receive_timeout=20,
                                )
                                await asyncio.wait_for(communicate.save(part_file), timeout=20.0)

                            if sys.platform == "win32":
                                loop = asyncio.SelectorEventLoop()
                                asyncio.set_event_loop(loop)
                                try:
                                    loop.run_until_complete(_fetch_edge_audio())
                                    loop.run_until_complete(loop.shutdown_asyncgens())
                                finally:
                                    asyncio.set_event_loop(None)
                                    loop.close()
                            else:
                                asyncio.run(_fetch_edge_audio())
                        elif getattr(self, "edge_tts_cli", None):
                            subprocess.run([
                                self.edge_tts_cli,
                                "--text", text,
                                "--voice", voice,
                                f"--rate={rate}",
                                "--write-media", part_file
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)

                        if os.path.exists(part_file) and os.path.getsize(part_file) > 0:
                            os.replace(part_file, tmp_file)
                    finally:
                        if os.path.exists(part_file):
                            try:
                                os.remove(part_file)
                            except OSError:
                                pass

                if os.path.exists(tmp_file) and os.path.getsize(tmp_file) > 0:
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
