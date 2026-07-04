import time
from PyQt6.QtCore import QThread, pyqtSignal
import ts3

class TS3ClientThread(QThread):
    # Sends a list of dictionaries: [{"name": "User1", "talking": True}, ...]
    clients_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.running = True
        self.ts3conn = None

    def run(self):
        while self.running:
            try:
                if not self.ts3conn:
                    self.ts3conn = ts3.query.TS3ClientConnection("localhost", port=25639)
                    # Use auth key if provided, else it might fail, but let's try
                    if self.api_key:
                        self.ts3conn.exec_("auth", apikey=self.api_key)
                    self.ts3conn.exec_("use")

                # Poll clientlist
                resp = self.ts3conn.exec_("clientlist", "-voice")
                clients = []
                # response parsed is a list of dictionaries
                for client in resp.parsed:
                    # ignore ServerQuery clients
                    if client.get("client_type") == "1":
                        continue
                        
                    name = client.get("client_nickname", "Unknown")
                    talking = client.get("client_flag_talking") == "1"
                    clients.append({"name": name, "talking": talking})
                    
                self.clients_updated.emit(clients)
                
                # Sleep a bit to prevent spamming
                time.sleep(0.5)

            except ts3.query.TS3QueryError as e:
                self.error_occurred.emit(f"TS3 Query Error: {e.resp.error['msg']}")
                time.sleep(2) # Backoff
            except Exception as e:
                self.error_occurred.emit(f"Connection lost or error: {e}")
                self.ts3conn = None # force reconnect
                time.sleep(2) # Backoff

    def stop(self):
        self.running = False
        if self.ts3conn:
            try:
                self.ts3conn.close()
            except:
                pass
        self.wait()
