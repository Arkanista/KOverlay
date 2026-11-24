import array
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time

# Process/application name patterns per voice backend (lowercase)
_BACKEND_PATTERNS = {
    "ts3": ("ts3client", "teamspeak", "ts3"),
    "mumble": ("mumble",),
    "discord": ("discord", "vesktop", "equibop", "armcord", "webcord"),
}


def _find_voip_sink_input(backend: str) -> str | None:
    """Finds the PulseAudio/PipeWire sink-input index for the active VoIP app."""
    if not shutil.which("pactl"):
        return None
    try:
        res = subprocess.run(
            ["pactl", "list", "sink-inputs"],
            capture_output=True,
            text=True,
            timeout=1.5,
            env={**os.environ, "LC_ALL": "C"},
        )
        if res.returncode != 0:
            return None
    except Exception:
        return None

    patterns = _BACKEND_PATTERNS.get(backend, ())
    if not patterns:
        patterns = tuple(p for pats in _BACKEND_PATTERNS.values() for p in pats)

    current_idx = None
    current_props = []
    for line in res.stdout.splitlines():
        m = re.match(r"^Sink Input #(\d+)", line)
        if m:
            if current_idx is not None:
                blob = " ".join(current_props).lower()
                if any(p in blob for p in patterns):
                    return current_idx
            current_idx = m.group(1)
            current_props = []
        elif current_idx is not None:
            low = line.strip().lower()
            if (
                "application.process.binary" in low
                or "application.name" in low
                or "node.name" in low
                or "media.name" in low
            ):
                current_props.append(low)

    if current_idx is not None:
        blob = " ".join(current_props).lower()
        if any(p in blob for p in patterns):
            return current_idx
    return None


def find_sink_input_by_pid(pid: int, player_name: str | None = None) -> str | None:
    """Finds the PulseAudio/PipeWire sink-input index owned by the given process PID (or player name fallback)."""
    if (not pid and not player_name) or not shutil.which("pactl"):
        return None
    try:
        res = subprocess.run(
            ["pactl", "list", "sink-inputs"],
            capture_output=True,
            text=True,
            timeout=1.0,
            env={**os.environ, "LC_ALL": "C"},
        )
        if res.returncode != 0:
            return None
    except Exception:
        return None

    target_pid = f'application.process.id = "{pid}"' if pid else None
    target_name = player_name.lower() if player_name else None
    current_idx = None
    name_matches = []
    for line in res.stdout.splitlines():
        m = re.match(r"^Sink Input #(\d+)", line)
        if m:
            current_idx = m.group(1)
        elif current_idx is not None:
            if target_pid and target_pid in line:
                return current_idx
            if target_name:
                low = line.strip().lower()
                if (
                    f'media.name = "{target_name}"' in low
                    or f'application.process.binary = "{target_name}"' in low
                    or f'application.name = "{target_name}"' in low
                ):
                    name_matches.append(current_idx)
    return name_matches[-1] if name_matches else None


def set_sink_input_volume_pct(sink_idx: str, pct: int) -> bool:
    """Sets the volume of a PulseAudio/PipeWire sink-input in percent (0..100)."""
    if not sink_idx or not shutil.which("pactl"):
        return False
    pct = max(0, min(100, int(pct)))
    try:
        res = subprocess.run(
            ["pactl", "set-sink-input-volume", str(sink_idx), f"{pct}%"],
            capture_output=True,
            timeout=0.5,
        )
        return res.returncode == 0
    except Exception:
        return False


class VoipAudioMonitor:
    """
    Monitors whether someone on the userlist is both marked as talking
    AND actually producing audio on the VoIP client's output stream
    (filtering out silent Push-to-Talk key-ups).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_once(config)
            elif config is not None:
                cls._instance.config = config
            return cls._instance

    def _init_once(self, config):
        self.config = config or {}
        self._state_lock = threading.Lock()
        self._has_active_speaker = False
        self._tts_playing = False
        self._last_audio_ts = 0.0
        self._simulated_duck_until = 0.0
        self._pending_test_duck = None  # (delay_sec, duration_sec)
        self._stream_active = False
        self._running = True
        self._parec_proc = None
        # -48 dBFS ~= 0.004 normalized RMS (catches quiet speech, ignores silence)
        self._rms_threshold = 0.004

        self._worker = threading.Thread(target=self._monitor_loop, daemon=True)
        self._worker.start()

    def set_talking_users(self, clients: list):
        """Updates whether any non-self user in the current channel is talking."""
        active = any(
            bool(c.get("talking", False)) and not bool(c.get("is_self", False))
            for c in (clients or [])
        )
        with self._state_lock:
            self._has_active_speaker = active

    def set_tts_playing(self, playing: bool):
        pending = None
        with self._state_lock:
            self._tts_playing = bool(playing)
            if playing and self._pending_test_duck is not None:
                pending = self._pending_test_duck
                self._pending_test_duck = None
        if pending is not None:
            delay_sec, duration_sec = pending

            def _delayed_trigger():
                time.sleep(delay_sec)
                self.trigger_simulated_duck(duration_sec)

            threading.Thread(target=_delayed_trigger, daemon=True).start()

    def schedule_test_duck_on_next_play(self, delay_sec: float = 0.9, duration_sec: float = 1.8):
        """Arms a simulated duck to trigger right after the next TTS playback actually starts."""
        with self._state_lock:
            self._pending_test_duck = (max(0.1, float(delay_sec)), max(0.2, float(duration_sec)))

    def trigger_simulated_duck(self, duration_sec: float = 2.0):
        """Temporarily forces ducking for dry-run testing in Settings."""
        with self._state_lock:
            self._simulated_duck_until = time.monotonic() + max(0.1, float(duration_sec))

    def should_duck(self) -> bool:
        """Returns True when TTS should be ducked right now."""
        cfg = self.config if isinstance(self.config, dict) else {}
        if not cfg.get("tts_ducking_enabled", True):
            return False

        release_ms = max(0, int(cfg.get("tts_duck_release_ms", 80)))
        now = time.monotonic()

        with self._state_lock:
            if now < self._simulated_duck_until:
                return True
            if not self._has_active_speaker:
                return False
            # If we have an active Linux audio stream monitor, require real audio
            if self._stream_active:
                return (now - self._last_audio_ts) * 1000.0 <= release_ms
            # Fallback (e.g. Windows or no parec/pactl): rely on userlist talking state
            return True

    def _stop_parec(self):
        proc = self._parec_proc
        self._parec_proc = None
        with self._state_lock:
            self._stream_active = False
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _monitor_loop(self):
        if sys.platform == "win32":
            return
        has_parec = shutil.which("parec") is not None
        if not has_parec:
            return

        last_needed_ts = 0.0
        while self._running:
            cfg = self.config if isinstance(self.config, dict) else {}
            enabled = cfg.get("tts_ducking_enabled", True) and cfg.get("tts_enabled", False)
            with self._state_lock:
                needed_now = enabled and (self._has_active_speaker or self._tts_playing)

            now = time.monotonic()
            if needed_now:
                last_needed_ts = now
            elif self._parec_proc is not None and (now - last_needed_ts) > 2.0:
                self._stop_parec()

            if not needed_now and self._parec_proc is None:
                time.sleep(0.05)
                continue

            if self._parec_proc is None:
                backend = cfg.get("voice_backend", "ts3")
                sink_idx = _find_voip_sink_input(backend)
                if not sink_idx:
                    time.sleep(0.2)
                    continue
                try:
                    self._parec_proc = subprocess.Popen(
                        [
                            "parec",
                            f"--monitor-stream={sink_idx}",
                            "--format=s16le",
                            "--rate=8000",
                            "--channels=1",
                            "--latency-msec=20",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    with self._state_lock:
                        self._stream_active = True
                except Exception:
                    self._stop_parec()
                    time.sleep(0.5)
                    continue

            # Read 20 ms of 8kHz mono s16le (160 samples = 320 bytes)
            proc = self._parec_proc
            try:
                chunk = proc.stdout.read(320)
                if not chunk:
                    self._stop_parec()
                    time.sleep(0.1)
                    continue
                if len(chunk) >= 2:
                    samples = array.array("h")
                    samples.frombytes(chunk[: len(chunk) - (len(chunk) % 2)])
                    if samples:
                        sum_sq = sum(s * s for s in samples)
                        rms = math.sqrt(sum_sq / len(samples)) / 32768.0
                        if rms >= self._rms_threshold:
                            with self._state_lock:
                                self._last_audio_ts = time.monotonic()
            except Exception:
                self._stop_parec()
                time.sleep(0.2)

    def stop(self):
        self._running = False
        self._stop_parec()


def get_voip_audio_monitor(config=None) -> VoipAudioMonitor:
    return VoipAudioMonitor(config)
