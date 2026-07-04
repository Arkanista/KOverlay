import json
import os

CONFIG_FILE = os.path.expanduser("~/.config/ts3-overlay/config.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"api_key": "", "opacity": 0.8}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {"api_key": "", "opacity": 0.8}

def save_config(config_data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")
