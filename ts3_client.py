import time
import socket
from PyQt6.QtCore import QThread, pyqtSignal

class TS3ClientThread(QThread):
    clients_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.running = True
        self.sock = None
        self.buf = ""

    def connect_ts3(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        
        self.buf = ""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect(("127.0.0.1", 25639))
        self.sock.settimeout(2.0)
        
        if self.api_key:
            self._send_cmd(f"auth apikey={self.api_key}")
            resp = self._read_until("error id=")
            if "error id=0" not in resp:
                raise Exception(f"Auth failed: {resp}")
                
        self._send_cmd("use")
        resp = self._read_until("error id=")
        if "error id=0" not in resp:
            raise Exception(f"Use failed: {resp}")

    def _send_cmd(self, cmd):
        self.sock.sendall((cmd + "\n").encode('utf-8'))

    def _read_until(self, target, max_lines=100):
        lines = []
        for _ in range(max_lines):
            while '\n' not in self.buf:
                data = self.sock.recv(4096)
                if not data:
                    raise Exception("Socket closed")
                self.buf += data.decode('utf-8', errors='replace')
            
            line, self.buf = self.buf.split('\n', 1)
            line = line.strip()
            lines.append(line)
            if target in line:
                return "\n".join(lines)
        return "\n".join(lines)

    def _parse_clientlist(self, data, filter_cid=None):
        clients = []
        for line in data.split('\n'):
            if line.startswith("error id="):
                continue
            if not line:
                continue
            
            users = line.split('|')
            for user in users:
                parts = user.split(' ')
                client_dict = {}
                for p in parts:
                    if '=' in p:
                        k, v = p.split('=', 1)
                        # Basic unescape
                        v = v.replace(r'\s', ' ').replace(r'\/', '/').replace(r'\p', '|')
                        client_dict[k] = v
                
                if client_dict.get('client_type') == '1':
                    continue # ServerQuery client
                    
                if filter_cid and client_dict.get('cid') != filter_cid:
                    continue
                    
                name = client_dict.get('client_nickname', 'Unknown')
                talking = client_dict.get('client_flag_talking') == '1'
                
                if 'clid' in client_dict:
                    clients.append({"name": name, "talking": talking})
        return clients

    def run(self):
        while self.running:
            try:
                if not self.sock:
                    self.connect_ts3()

                self._send_cmd("whoami")
                resp_whoami = self._read_until("error id=")
                
                my_cid = None
                if "error id=0" in resp_whoami:
                    for part in resp_whoami.replace('|', ' ').split(' '):
                        if part.startswith("cid="):
                            my_cid = part.split('=', 1)[1]
                            break

                self._send_cmd("clientlist -voice")
                resp = self._read_until("error id=")
                
                if "error id=0" not in resp:
                    # Not connected to a server or empty response
                    self.clients_updated.emit([])
                else:
                    clients = self._parse_clientlist(resp, filter_cid=my_cid)
                    self.clients_updated.emit(clients)
                
                time.sleep(0.5)

            except Exception as e:
                self.error_occurred.emit(f"Connection error: {e}")
                self.sock = None
                time.sleep(2) # Backoff

    def stop(self):
        self.running = False
        if self.sock:
            try: self.sock.close()
            except: pass
        self.wait()
