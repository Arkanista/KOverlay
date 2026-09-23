import time
import socket
import json
from PyQt6.QtCore import QThread, pyqtSignal

class MumbleClientThread(QThread):
    clients_updated = pyqtSignal(list, object)
    error_occurred = pyqtSignal(str)

    def __init__(self, host="127.0.0.1", port=25640, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = int(port)
        self.running = True
        self.sock = None
        self.buf = ""

    def connect_mumble(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

        self.buf = ""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(3.0)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(2.0)

    def run(self):
        while self.running:
            try:
                if not self.sock:
                    self.connect_mumble()

                # Read lines separated by '\n'
                while '\n' not in self.buf:
                    if not self.running:
                        break
                    if len(self.buf) > 1024 * 1024:
                        self.buf = ""
                        raise Exception("Buffer exceeded limit")
                    try:
                        data = self.sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not data:
                        raise Exception("Mumble plugin disconnected")
                    self.buf += data.decode('utf-8', errors='replace')

                if not self.running:
                    break

                line, self.buf = self.buf.split('\n', 1)
                line = line.strip()
                if line:
                    try:
                        payload = json.loads(line)
                        if payload.get("type") == "update":
                            clients = payload.get("clients", [])
                            channel_id = payload.get("channel_id")
                            self.clients_updated.emit(clients, channel_id)
                    except json.JSONDecodeError:
                        pass

            except Exception as e:
                if not self.running:
                    break
                self.error_occurred.emit(f"Mumble connection error: {e}")
                # Do not emit empty clients list on transient socket disconnect/reconnect.
                # This prevents the overlay from wiping all users, triggering ghost leave/join TTS, and flickering.
                if self.sock:
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                self.sock = None
                time.sleep(1)  # 1s backoff before reconnect

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        self.wait()
