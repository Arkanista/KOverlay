#!/bin/bash
# Zmienia katalog na ten w którym znajduje się skrypt
cd "$(dirname "$0")"

# Aktywuje wirtualne środowisko i uruchamia aplikację
source venv/bin/activate
exec python3 koverlay.py
