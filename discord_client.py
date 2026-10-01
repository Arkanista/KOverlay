import os
import sys
import time
import json
import uuid
import struct
import socket
import urllib.request
from PyQt6.QtCore import QThread, pyqtSignal

# Standard StreamKit Overlay Client ID
DISCORD_CLIENT_ID = "207646673902501888"
TOKEN_ENDPOINT = "https://streamkit.discord.com/overlay/token"

class DiscordIpcTransport:
    """Cross-platform transport for Discord IPC (UNIX Domain Socket on Linux/macOS, Named Pipe on Windows)."""
    def __init__(self):
        self.sock = None
        self.win_handle = None

    def connect(self):
        self.close()
        if sys.platform == "win32":
            return self._connect_windows()
        else:
            return self._connect_unix()

    def _connect_unix(self):
        candidates = []
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}" if hasattr(os, "getuid") else "/tmp")
        for i in range(10):
            candidates.append(os.path.join(runtime_dir, f"discord-ipc-{i}"))
        for i in range(10):
            candidates.append(os.path.join("/tmp", f"discord-ipc-{i}"))

        for path in candidates:
            if os.path.exists(path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(3.0)
                    s.connect(path)
                    s.settimeout(2.0)
                    self.sock = s
                    return True
                except Exception:
                    continue
        return False

    def _connect_windows(self):
        import ctypes
        from ctypes import wintypes

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        kernel32 = ctypes.windll.kernel32

        for i in range(10):
            pipe_path = f"\\\\.\\pipe\\discord-ipc-{i}"
            handle = kernel32.CreateFileW(
                pipe_path,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None
            )
            if handle != INVALID_HANDLE_VALUE:
                self.win_handle = handle
                return True
        return False

    def send_raw(self, data: bytes):
        if self.sock:
            self.sock.sendall(data)
        elif self.win_handle:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            written = wintypes.DWORD()
            success = kernel32.WriteFile(self.win_handle, data, len(data), ctypes.byref(written), None)
            if not success:
                raise OSError("Failed to write to Windows named pipe")
        else:
            raise OSError("Not connected to Discord IPC")

    def recv_exact(self, length: int) -> bytes:
        received = b""
        if self.sock:
            while len(received) < length:
                chunk = self.sock.recv(min(4096, length - len(received)))
                if not chunk:
                    raise ConnectionResetError("Discord IPC socket closed")
                received += chunk
            return received
        elif self.win_handle:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            while len(received) < length:
                to_read = min(4096, length - len(received))
                buf = ctypes.create_string_buffer(to_read)
                read_bytes = wintypes.DWORD()
                success = kernel32.ReadFile(self.win_handle, buf, to_read, ctypes.byref(read_bytes), None)
                if not success or read_bytes.value == 0:
                    raise ConnectionResetError("Discord IPC named pipe closed")
                received += buf.raw[:read_bytes.value]
            return received
        else:
            raise OSError("Not connected to Discord IPC")

    def set_timeout(self, timeout_sec: float):
        if self.sock:
            self.sock.settimeout(timeout_sec)

    def close(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.win_handle:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.CloseHandle(self.win_handle)
            except Exception:
                pass
            self.win_handle = None


class DiscordClientThread(QThread):
    clients_updated = pyqtSignal(list, object)
    error_occurred = pyqtSignal(str)

    def __init__(self, client_id=DISCORD_CLIENT_ID, access_token="", token_save_callback=None, parent=None):
        super().__init__(parent)
        self.client_id = client_id or DISCORD_CLIENT_ID
        self.access_token = access_token or ""
        self.token_save_callback = token_save_callback
        self.running = True
        self.transport = DiscordIpcTransport()
        self.current_channel_id = None
        self.channel_members = {}  # {user_id: {"clid": user_id, "name": nick, "talking": False}}

    def _send_packet(self, opcode: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", opcode, len(body))
        self.transport.send_raw(header + body)

    def _recv_packet(self, timeout=None):
        if timeout is not None:
            self.transport.set_timeout(timeout)
        try:
            hdr = self.transport.recv_exact(8)
            opcode, length = struct.unpack("<II", hdr)
            body = self.transport.recv_exact(length)
            data = json.loads(body.decode("utf-8", errors="replace"))
            return opcode, data
        except socket.timeout:
            return None, None

    def _send_cmd(self, cmd: str, args=None, evt=None):
        nonce = str(uuid.uuid4())
        packet = {"cmd": cmd, "nonce": nonce}
        if args is not None:
            packet["args"] = args
        if evt is not None:
            packet["evt"] = evt
        self._send_packet(1, packet)
        return nonce

    def _extract_display_name(self, state_or_user, fallback_user=None):
        """Extracts guild nickname, global name, or username."""
        nick = state_or_user.get("nick")
        if nick and nick.strip():
            return nick.strip()

        user = state_or_user.get("user") or fallback_user or {}
        global_name = user.get("global_name")
        if global_name and global_name.strip():
            return global_name.strip()

        username = user.get("username")
        if username and username.strip():
            return username.strip()

        return "Unknown"

    def _exchange_code_for_token(self, code: str) -> str:
        req = urllib.request.Request(
            TOKEN_ENDPOINT,
            data=json.dumps({"code": code}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "KOverlay"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data.get("access_token", "")

    def _authenticate(self):
        # 1. Try saved access token if available
        if self.access_token:
            self._send_cmd("AUTHENTICATE", args={"access_token": self.access_token})
            op, resp = self._recv_packet(timeout=5.0)
            if resp and resp.get("cmd") == "AUTHENTICATE" and resp.get("evt") != "ERROR":
                return True
            # Token expired or invalid
            self.access_token = ""
            if self.token_save_callback:
                self.token_save_callback("")

        # 2. Trigger AUTHORIZE flow (shows Discord popup if first time)
        self._send_cmd("AUTHORIZE", args={
            "client_id": self.client_id,
            "scopes": ["rpc", "messages.read"],
            "prompt": "consent"
        })

        # Wait up to 60s for user authorization in Discord UI
        start_wait = time.time()
        while self.running and (time.time() - start_wait < 60.0):
            op, resp = self._recv_packet(timeout=1.0)
            if not resp:
                continue
            if resp.get("cmd") == "AUTHORIZE":
                if resp.get("evt") == "ERROR":
                    raise Exception(f"Authorization error: {resp.get('data', {}).get('message')}")
                code = resp.get("data", {}).get("code")
                if code:
                    token = self._exchange_code_for_token(code)
                    if token:
                        self.access_token = token
                        if self.token_save_callback:
                            self.token_save_callback(token)
                        # Authenticate with the newly acquired token
                        self._send_cmd("AUTHENTICATE", args={"access_token": self.access_token})
                        op, auth_resp = self._recv_packet(timeout=5.0)
                        if auth_resp and auth_resp.get("cmd") == "AUTHENTICATE" and auth_resp.get("evt") != "ERROR":
                            return True
                    raise Exception("Failed to retrieve access token from Discord StreamKit endpoint")
        raise TimeoutError("Timed out waiting for Discord user authorization")

    def _subscribe_channel_events(self, channel_id):
        if not channel_id:
            return
        for evt in ["SPEAKING_START", "SPEAKING_STOP", "VOICE_STATE_CREATE", "VOICE_STATE_DELETE", "VOICE_STATE_UPDATE"]:
            self._send_cmd("SUBSCRIBE", args={"channel_id": channel_id}, evt=evt)

    def _unsubscribe_channel_events(self, channel_id):
        if not channel_id:
            return
        for evt in ["SPEAKING_START", "SPEAKING_STOP", "VOICE_STATE_CREATE", "VOICE_STATE_DELETE", "VOICE_STATE_UPDATE"]:
            try:
                self._send_cmd("UNSUBSCRIBE", args={"channel_id": channel_id}, evt=evt)
            except Exception:
                pass

    def _emit_clients(self):
        clients = list(self.channel_members.values())
        self.clients_updated.emit(clients, self.current_channel_id)

    def run(self):
        while self.running:
            try:
                # Connect to Discord IPC
                if not self.transport.connect():
                    time.sleep(2.0)
                    continue

                # Handshake
                self._send_packet(0, {"v": 1, "client_id": self.client_id})
                op, ready = self._recv_packet(timeout=5.0)
                if not ready or ready.get("evt") != "READY":
                    raise ConnectionError("Discord IPC handshake failed")

                # Authenticate
                if not self._authenticate():
                    raise ConnectionError("Discord authentication failed")

                # Subscribe to global voice channel change
                self._send_cmd("SUBSCRIBE", evt="VOICE_CHANNEL_SELECT")

                # Query current active voice channel
                self._send_cmd("GET_SELECTED_VOICE_CHANNEL")

                # Event loop
                while self.running:
                    op, msg = self._recv_packet(timeout=1.0)
                    if not msg:
                        continue

                    cmd = msg.get("cmd")
                    evt = msg.get("evt")
                    data = msg.get("data")

                    if cmd == "GET_SELECTED_VOICE_CHANNEL":
                        if data and data.get("id"):
                            new_cid = data.get("id")
                            if new_cid != self.current_channel_id:
                                self._unsubscribe_channel_events(self.current_channel_id)
                                self.current_channel_id = new_cid
                                self._subscribe_channel_events(new_cid)

                            self.channel_members.clear()
                            for st in data.get("voice_states", []):
                                u = st.get("user", {})
                                uid = u.get("id")
                                if uid:
                                    nick = self._extract_display_name(st, u)
                                    self.channel_members[uid] = {
                                        "clid": uid,
                                        "name": nick,
                                        "talking": False
                                    }
                            self._emit_clients()
                        else:
                            if self.current_channel_id:
                                self._unsubscribe_channel_events(self.current_channel_id)
                            self.current_channel_id = None
                            self.channel_members.clear()
                            self._emit_clients()

                    elif evt == "VOICE_CHANNEL_SELECT":
                        new_cid = data.get("channel_id") if data else None
                        if new_cid != self.current_channel_id:
                            if self.current_channel_id:
                                self._unsubscribe_channel_events(self.current_channel_id)
                            self.current_channel_id = new_cid
                            self.channel_members.clear()
                            if new_cid:
                                self._subscribe_channel_events(new_cid)
                                self._send_cmd("GET_SELECTED_VOICE_CHANNEL")
                            else:
                                self._emit_clients()

                    elif evt == "SPEAKING_START":
                        uid = data.get("user_id") if data else None
                        if uid and uid in self.channel_members:
                            self.channel_members[uid]["talking"] = True
                            self._emit_clients()

                    elif evt == "SPEAKING_STOP":
                        uid = data.get("user_id") if data else None
                        if uid and uid in self.channel_members:
                            self.channel_members[uid]["talking"] = False
                            self._emit_clients()

                    elif evt == "VOICE_STATE_CREATE":
                        # User joined voice channel
                        u = data.get("user", {}) if data else {}
                        uid = u.get("id")
                        if uid:
                            nick = self._extract_display_name(data, u)
                            self.channel_members[uid] = {
                                "clid": uid,
                                "name": nick,
                                "talking": False
                            }
                            self._emit_clients()

                    elif evt == "VOICE_STATE_DELETE":
                        # User left voice channel
                        u = data.get("user", {}) if data else {}
                        uid = u.get("id")
                        if uid and uid in self.channel_members:
                            del self.channel_members[uid]
                            self._emit_clients()

                    elif evt == "VOICE_STATE_UPDATE":
                        # User nickname or mute state changed
                        u = data.get("user", {}) if data else {}
                        uid = u.get("id")
                        if uid and uid in self.channel_members:
                            nick = self._extract_display_name(data, u)
                            self.channel_members[uid]["name"] = nick
                            self._emit_clients()

            except Exception as e:
                if not self.running:
                    break
                self.error_occurred.emit(f"Discord connection error: {e}")
                self.transport.close()
                time.sleep(2.0)

    def stop(self):
        self.running = False
        self.transport.close()
        self.wait(1500)
