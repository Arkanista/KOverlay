import os
import sys
import tempfile
import hashlib
import shutil
import subprocess
import threading
import queue
import time
import importlib.util
import re

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
            return cls._instance

    def _init_once(self, config):
        if config is None:
            config = {}
            
        self.message_queue = queue.Queue(maxsize=5)
        self.is_running = True
        self.edge_tts_installed = importlib.util.find_spec("edge_tts") is not None
        
        # Setup persistent cache directory
        self.cache_dir = os.path.expanduser("~/.cache/ts3-overlay/tts_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Cleanup old files
        retention_days = config.get("tts_cache_retention_days", 30)
        self._cleanup_old_cache(retention_days)
        
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

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

    def _play_sync(self, item):
        text = item["text"]
        voice = item["voice"]
        vol = item["volume"]
        rate = item["rate"]
        safe_text = "".join(c for c in text if c.isalnum() or c in " _-.")

        if self.edge_tts_installed and shutil.which("mpv"):
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
                    import edge_tts
                    import asyncio
                    communicate = edge_tts.Communicate(text, voice, rate=rate)
                    asyncio.run(communicate.save(tmp_file))
                    
                # Use subprocess.run to BLOCK until mpv finishes playing the audio
                # Added silenceremove filter to strip generated silence at start and end
                subprocess.run([
                    "mpv", 
                    "--no-video", 
                    "--no-terminal", 
                    f"--volume={vol}", 
                    # Using -70dB to prevent clipping the soft attack of the first consonant
                    "--af=silenceremove=start_periods=1:start_duration=0:start_threshold=-70dB,silenceremove=stop_periods=-1:stop_duration=0:stop_threshold=-70dB",
                    tmp_file
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

# Global accessor
def get_tts_manager(config=None):
    """Returns the singleton instance of TTSManager."""
    return TTSManager(config)
