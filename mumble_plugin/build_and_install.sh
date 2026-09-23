#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS_DIR="$HOME/.local/share/Mumble/Mumble/Plugins"

echo "=== Building KOverlay Mumble Plugin ==="
cd "$SCRIPT_DIR"

if command -v g++ >/dev/null 2>&1; then
    echo "Compiling with g++..."
    g++ -O2 -Wall -fPIC -std=c++17 -Iinclude koverlay_mumble.cpp -o koverlay_mumble.so -shared -lpthread
elif command -v clang++ >/dev/null 2>&1; then
    echo "Compiling with clang++..."
    clang++ -O2 -Wall -fPIC -std=c++17 -Iinclude koverlay_mumble.cpp -o koverlay_mumble.so -shared -lpthread
else
    echo "Error: Neither g++ nor clang++ was found. Please install a C++ compiler (e.g. 'sudo pacman -S gcc')."
    exit 1
fi

echo "=== Installing plugin to Mumble ==="
mkdir -p "$PLUGINS_DIR"
cp -f "$SCRIPT_DIR/koverlay_mumble.so" "$PLUGINS_DIR/"

echo "Success! Plugin copied to: $PLUGINS_DIR/koverlay_mumble.so"
echo "Make sure to enable 'KOverlay Mumble Plugin' in Mumble under Configure -> Settings -> Plugins."
