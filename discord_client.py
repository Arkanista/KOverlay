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
DEFAULT_CLIENT_ID = DISCORD_CLIENT_ID
TOKEN_ENDPOINT = "https://streamkit.discord.com/overlay/token"

class DiscordIpcTransport:
    """Cross-platform transport for Discord IPC (UNIX Domain Socket on Linux/macOS, Named Pipe on Windows)."""
    def __init__(self):
        self.sock = None
        self.win_handle = None
        self.timeout = 2.0
        self._closing = False

    def connect(self):
        self.close()
        self._closing = False
        if sys.platform == "win32":
            return self._connect_windows()
        else:
            return self._connect_unix()

    def _connect_unix(self):
        candidates = []
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}" if hasattr(os, "getuid") else "/tmp")
        ipc_dirs = [
            runtime_dir,
            os.path.join(runtime_dir, "app", "com.discordapp.Discord"),
            os.path.join(runtime_dir, "app", "com.discordapp.DiscordCanary"),
            os.path.join(runtime_dir, "app", "com.discordapp.DiscordPTB"),
            os.path.join(runtime_dir, "app", "dev.vencord.Vesktop"),
            os.path.join(runtime_dir, "snap.discord"),
            "/tmp",
        ]
        for d in ipc_dirs:
            for i in range(10):
                candidates.append(os.path.join(d, f"discord-ipc-{i}"))

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
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]

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
            if handle != INVALID_HANDLE_VALUE and handle != -1 and handle != 0:
                self.win_handle = handle
                self._closing = False
                return True
        return False

    def send_raw(self, data: bytes):
        if self.sock:
            self.sock.sendall(data)
        elif self.win_handle:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            kernel32.WriteFile.argtypes = [
                wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
            ]
            kernel32.WriteFile.restype = wintypes.BOOL
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
            kernel32.PeekNamedPipe.argtypes = [
                wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)
            ]
            kernel32.PeekNamedPipe.restype = wintypes.BOOL
            kernel32.ReadFile.argtypes = [
                wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
            ]
            kernel32.ReadFile.restype = wintypes.BOOL

            start_time = time.time()
            avail = wintypes.DWORD()
            while len(received) < length:
                handle = self.win_handle
                if self._closing or not handle:
                    raise ConnectionResetError("Discord IPC handle closed")

                success = kernel32.PeekNamedPipe(
                    handle, None, 0, None, ctypes.byref(avail), None
                )
                if not success:
                    raise ConnectionResetError("Discord IPC named pipe broken")

                if avail.value == 0:
                    if self.timeout is not None and (time.time() - start_time) >= self.timeout:
                        raise TimeoutError("Discord IPC read timed out")
                    time.sleep(0.02)
                    continue

                to_read = min(avail.value, length - len(received))
                buf = ctypes.create_string_buffer(to_read)
                read_bytes = wintypes.DWORD()
                success = kernel32.ReadFile(handle, buf, to_read, ctypes.byref(read_bytes), None)
                if not success or read_bytes.value == 0:
                    raise ConnectionResetError("Discord IPC named pipe closed")
                received += buf.raw[:read_bytes.value]
                start_time = time.time()
            return received
        else:
            raise OSError("Not connected to Discord IPC")

    def set_timeout(self, timeout_sec: float):
        self.timeout = timeout_sec
        if self.sock:
            self.sock.settimeout(timeout_sec)

    send = send_raw
    recv = recv_exact

    def close(self):
        self._closing = True
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
            handle = self.win_handle
            self.win_handle = None
            try:
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.windll.kernel32
                kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
                kernel32.CancelIoEx.restype = wintypes.BOOL
                kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel32.CloseHandle.restype = wintypes.BOOL
                kernel32.CancelIoEx(handle, None)
                kernel32.CloseHandle(handle)
            except Exception:
                pass


class DiscordClientThread(QThread):
    clients_updated = pyqtSignal(list, object)
    error_occurred = pyqtSignal(str)
    token_updated = pyqtSignal(str)

    def __init__(self, client_id=DISCORD_CLIENT_ID, access_token="", token_save_callback=None, parent=None):
        super().__init__(parent)
        self.client_id = client_id or DISCORD_CLIENT_ID
        self.access_token = access_token or ""
        self.token_save_callback = token_save_callback
        if token_save_callback is not None:
            self.token_updated.connect(token_save_callback)
        self.running = True
        self.transport = DiscordIpcTransport()
        self.local_user_id = None
        self.current_channel_id = None
        self._channel_synced = False
        self.channel_members = {}  # {user_id: {"clid": user_id, "name": nick, "talking": False, "is_self": bool, "status_icons": [...]}}

    def _send_packet(self, opcode: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", opcode, len(body))
        self.transport.send_raw(header + body)

    def _recv_packet(self, timeout=None):
        if timeout is not None:
            self.transport.set_timeout(timeout)
        try:
            while self.running:
                hdr = self.transport.recv_exact(8)
                opcode, length = struct.unpack("<II", hdr)
                body = self.transport.recv_exact(length)
                data = json.loads(body.decode("utf-8", errors="replace")) if length > 0 else {}
                if opcode == 2:
                    # CLOSE frame from Discord IPC
                    raise ConnectionResetError("Discord IPC closed by server")
                if opcode == 3:
                    # PING frame from Discord IPC -> reply with PONG (opcode 4)
                    try:
                        self._send_packet(4, data if isinstance(data, dict) else {})
                    except Exception:
                        pass
                    continue
                return opcode, data
            return None, None
        except (socket.timeout, TimeoutError):
            return None, None

    def _sleep_interruptible(self, seconds: float):
        deadline = time.time() + seconds
        while self.running and time.time() < deadline:
            time.sleep(0.05)

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
        if not isinstance(state_or_user, dict):
            state_or_user = {}
        nick = state_or_user.get("nick")
        if nick and str(nick).strip():
            return str(nick).strip()

        user = state_or_user.get("user") if isinstance(state_or_user.get("user"), dict) else (fallback_user or {})
        global_name = user.get("global_name")
        if global_name and str(global_name).strip():
            return str(global_name).strip()

        username = user.get("username")
        if username and str(username).strip():
            return str(username).strip()

        return "Unknown"

    def _extract_status_info(self, st: dict, fallback_user: dict = None):
        """
        Extracts Discord voice state flags and returns (status_icons_list, can_speak_bool).
        Available icons:
        - 'server_mute' / 'mute'
        - 'server_deaf' / 'deaf'
        - 'suppress'
        - 'stream'
        - 'video'
        - 'bot'
        """
        if not isinstance(st, dict):
            st = {}
        vs = st.get("voice_state")
        if not isinstance(vs, dict):
            vs = st
        u = st.get("user") if isinstance(st.get("user"), dict) else (fallback_user or {})

        # Top-level 'mute' in a voice_state wrapper indicates local mute by the client user
        local_mute = bool(st.get("mute", False)) if "voice_state" in st else False
        self_mute = bool(vs.get("self_mute", False) or st.get("self_mute", False))
        server_mute = bool(vs.get("mute", False))
        self_deaf = bool(vs.get("self_deaf", False) or st.get("self_deaf", False))
        server_deaf = bool(vs.get("deaf", False) or st.get("deaf", False))
        suppress = bool(vs.get("suppress", False) or st.get("suppress", False))
        self_video = bool(vs.get("self_video", False) or st.get("self_video", False) or st.get("video", False))
        self_stream = bool(vs.get("self_stream", False) or st.get("self_stream", False) or st.get("stream", False))
        is_bot = bool(u.get("bot", False))

        icons = []
        if server_mute:
            icons.append("server_mute")
        elif self_mute or local_mute:
            icons.append("mute")

        if server_deaf:
            icons.append("server_deaf")
        elif self_deaf:
            icons.append("deaf")

        if suppress:
            icons.append("suppress")
        if self_stream:
            icons.append("stream")
        if self_video:
            icons.append("video")
        if is_bot:
            icons.append("bot")

        can_speak = not (server_mute or self_mute or local_mute or server_deaf or self_deaf or suppress)
        return icons, can_speak

    def _build_member_entry(self, uid: str, st: dict, u: dict, prev_entry: dict = None) -> dict:
        nick = self._extract_display_name(st, u)
        if nick == "Unknown" and prev_entry and prev_entry.get("name"):
            nick = prev_entry["name"]
        icons, can_speak = self._extract_status_info(st, u)
        was_talking = bool(prev_entry.get("talking", False)) if prev_entry else False
        return {
            "clid": str(uid),
            "name": nick,
            "talking": was_talking and can_speak,
            "is_self": bool(self.local_user_id and str(uid) == str(self.local_user_id)),
            "status_icons": icons,
            "platform": "discord",
        }

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
        if not self.access_token:
            return False

        nonce = self._send_cmd("AUTHENTICATE", args={"access_token": self.access_token})
        deadline = time.time() + 5.0
        while self.running and time.time() < deadline:
            op, resp = self._recv_packet(timeout=max(0.2, deadline - time.time()))
            if not resp or not isinstance(resp, dict):
                continue
            if resp.get("cmd") == "AUTHENTICATE" or (nonce and resp.get("nonce") == nonce):
                if resp.get("evt") != "ERROR":
                    user_obj = (resp.get("data") or {}).get("user") or {}
                    if user_obj.get("id"):
                        self.local_user_id = str(user_obj.get("id"))
                    return True
                else:
                    # Explicit authentication rejection from Discord (token expired or revoked)
                    self.access_token = ""
                    self.token_updated.emit("")
                    return False

        # Timed out waiting for AUTHENTICATE response (do NOT wipe saved token on transient timeout)
        return False

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
                if not self.access_token:
                    # Not authorized: idle peacefully without connecting or prompting Discord
                    self._sleep_interruptible(1.0)
                    continue

                # Reset per-connection channel subscription state so reconnects always re-subscribe
                self.current_channel_id = None
                self._channel_synced = False
                self.channel_members.clear()

                # Connect to Discord IPC
                if not self.transport.connect():
                    self._sleep_interruptible(2.0)
                    continue

                # Handshake
                self._send_packet(0, {"v": 1, "client_id": self.client_id})
                op, ready = self._recv_packet(timeout=5.0)
                if not ready or ready.get("evt") != "READY":
                    raise ConnectionError("Discord IPC handshake failed")

                ready_user = ((ready.get("data") or {}).get("user") or {}) if isinstance(ready, dict) else {}
                if ready_user.get("id"):
                    self.local_user_id = str(ready_user.get("id"))

                # Authenticate silently using saved token
                if not self._authenticate():
                    self.transport.close()
                    self._sleep_interruptible(2.0)
                    continue

                # Subscribe to global voice channel change
                self._send_cmd("SUBSCRIBE", evt="VOICE_CHANNEL_SELECT")

                # Query current active voice channel
                self._send_cmd("GET_SELECTED_VOICE_CHANNEL")

                # Event loop
                while self.running:
                    op, msg = self._recv_packet(timeout=0.5)
                    if not msg or not isinstance(msg, dict):
                        continue

                    cmd = msg.get("cmd")
                    evt = msg.get("evt")
                    data = msg.get("data")

                    if cmd == "GET_SELECTED_VOICE_CHANNEL":
                        if isinstance(data, dict) and data.get("id"):
                            new_cid = str(data.get("id"))
                            if new_cid != self.current_channel_id or not self._channel_synced:
                                if self.current_channel_id and self.current_channel_id != new_cid:
                                    self._unsubscribe_channel_events(self.current_channel_id)
                                self.current_channel_id = new_cid
                                self._subscribe_channel_events(new_cid)

                            prev_members = dict(self.channel_members)
                            self.channel_members.clear()
                            for st in data.get("voice_states", []):
                                if not isinstance(st, dict):
                                    continue
                                u = st.get("user") if isinstance(st.get("user"), dict) else {}
                                uid = u.get("id")
                                if uid:
                                    uid_str = str(uid)
                                    self.channel_members[uid_str] = self._build_member_entry(
                                        uid_str, st, u, prev_members.get(uid_str)
                                    )
                            self._channel_synced = True
                            self._emit_clients()
                        else:
                            if self.current_channel_id:
                                self._unsubscribe_channel_events(self.current_channel_id)
                            self.current_channel_id = None
                            self._channel_synced = False
                            self.channel_members.clear()
                            self._emit_clients()

                    elif evt == "VOICE_CHANNEL_SELECT":
                        new_cid = str(data.get("channel_id")) if (isinstance(data, dict) and data.get("channel_id")) else None
                        if new_cid != self.current_channel_id:
                            if self.current_channel_id:
                                self._unsubscribe_channel_events(self.current_channel_id)
                            self.current_channel_id = new_cid
                            self._channel_synced = False
                            self.channel_members.clear()
                            if new_cid:
                                self._send_cmd("GET_SELECTED_VOICE_CHANNEL")
                            else:
                                self._emit_clients()

                    elif evt == "SPEAKING_START":
                        if not self._channel_synced:
                            continue
                        uid = str(data.get("user_id")) if (isinstance(data, dict) and data.get("user_id")) else None
                        if uid and uid in self.channel_members:
                            self.channel_members[uid]["talking"] = True
                            self._emit_clients()

                    elif evt == "SPEAKING_STOP":
                        if not self._channel_synced:
                            continue
                        uid = str(data.get("user_id")) if (isinstance(data, dict) and data.get("user_id")) else None
                        if uid and uid in self.channel_members:
                            self.channel_members[uid]["talking"] = False
                            self._emit_clients()

                    elif evt == "VOICE_STATE_CREATE":
                        if not self._channel_synced or not isinstance(data, dict):
                            continue
                        # User joined voice channel
                        u = data.get("user") if isinstance(data.get("user"), dict) else {}
                        uid = str(u.get("id")) if u.get("id") else None
                        if uid:
                            self.channel_members[uid] = self._build_member_entry(
                                uid, data, u, self.channel_members.get(uid)
                            )
                            self._emit_clients()

                    elif evt == "VOICE_STATE_DELETE":
                        if not self._channel_synced or not isinstance(data, dict):
                            continue
                        # User left voice channel
                        u = data.get("user") if isinstance(data.get("user"), dict) else {}
                        uid = str(u.get("id")) if u.get("id") else None
                        if uid:
                            # If the local user themselves left the active voice channel, reset channel state immediately
                            # so we never announce our own departure or leave stale channel members on screen.
                            if self.local_user_id and uid == str(self.local_user_id):
                                if self.current_channel_id:
                                    self._unsubscribe_channel_events(self.current_channel_id)
                                self.current_channel_id = None
                                self._channel_synced = False
                                self.channel_members.clear()
                                self._emit_clients()
                            elif uid in self.channel_members:
                                del self.channel_members[uid]
                                self._emit_clients()

                    elif evt == "VOICE_STATE_UPDATE":
                        if not self._channel_synced or not isinstance(data, dict):
                            continue
                        # User nickname or mute/deafen/status state changed
                        u = data.get("user") if isinstance(data.get("user"), dict) else {}
                        uid = str(u.get("id")) if u.get("id") else None
                        if uid:
                            self.channel_members[uid] = self._build_member_entry(
                                uid, data, u, self.channel_members.get(uid)
                            )
                            self._emit_clients()

            except Exception as e:
                if not self.running:
                    break
                self.error_occurred.emit(f"Discord connection error: {e}")
                self.transport.close()
                self._sleep_interruptible(2.0)

    def stop(self):
        self.running = False
        self.transport.close()
        self.wait(2000)


class DiscordAuthThread(QThread):
    auth_success = pyqtSignal(str)
    auth_failed = pyqtSignal(str)

    def __init__(self, client_id=DEFAULT_CLIENT_ID, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.transport = DiscordIpcTransport()
        self.running = True

    def _send_packet(self, op: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", op, len(data))
        self.transport.send_raw(header + data)

    def _recv_packet(self, timeout=5.0):
        if timeout is not None:
            self.transport.set_timeout(timeout)
        try:
            header_data = self.transport.recv_exact(8)
            op, length = struct.unpack("<II", header_data)
            body = self.transport.recv_exact(length)
            return op, json.loads(body.decode("utf-8", errors="replace"))
        except Exception:
            return None, None

    def _send_cmd(self, cmd: str, args: dict = None, evt: str = None):
        payload = {"cmd": cmd, "nonce": str(uuid.uuid4())}
        if args is not None:
            payload["args"] = args
        if evt is not None:
            payload["evt"] = evt
        self._send_packet(1, payload)

    def _exchange_code_for_token(self, code: str) -> str:
        req = urllib.request.Request(
            TOKEN_ENDPOINT,
            data=json.dumps({"code": code}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "KOverlay"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data.get("access_token", "")

    def run(self):
        try:
            if not self.transport.connect():
                self.auth_failed.emit("Could not connect to Discord. Make sure the Discord desktop app is running.")
                return

            # Handshake
            self._send_packet(0, {"v": 1, "client_id": self.client_id})
            op, ready = self._recv_packet(timeout=5.0)
            if not ready or ready.get("evt") != "READY":
                self.auth_failed.emit("Discord IPC handshake failed.")
                return

            # Prompt Discord for authorization
            self._send_cmd("AUTHORIZE", args={
                "client_id": self.client_id,
                "scopes": ["rpc", "messages.read"],
                "prompt": "consent"
            })

            start_wait = time.time()
            while self.running and (time.time() - start_wait < 60.0):
                op, resp = self._recv_packet(timeout=1.0)
                if not resp:
                    continue
                if resp.get("cmd") == "AUTHORIZE":
                    if resp.get("evt") == "ERROR":
                        err_msg = resp.get("data", {}).get("message", "Authorization denied in Discord.")
                        self.auth_failed.emit(f"Discord authorization error: {err_msg}")
                        return
                    code = resp.get("data", {}).get("code")
                    if code:
                        token = self._exchange_code_for_token(code)
                        if token:
                            self.auth_success.emit(token)
                            return
                        else:
                            self.auth_failed.emit("Failed to obtain access token from Discord.")
                            return
            if self.running:
                self.auth_failed.emit("Timed out waiting for authorization in Discord.")
        except Exception as e:
            self.auth_failed.emit(str(e))
        finally:
            self.transport.close()

    def cancel(self):
        self.running = False
        self.transport.close()
        self.wait(1000)
