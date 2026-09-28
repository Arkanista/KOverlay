#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS_DIR="$HOME/.local/share/Mumble/Mumble/Plugins"

echo "=== Building KOverlay Mumble Plugin ==="

# Create a temporary directory in user space so compilation never fails due to read-only install directories (e.g. /opt/koverlay)
BUILD_DIR=$(mktemp -d /tmp/koverlay_mumble_build.XXXXXX)
trap 'rm -rf "$BUILD_DIR"' EXIT

TARGET_SO="$BUILD_DIR/koverlay_mumble.so"

if command -v g++ >/dev/null 2>&1; then
    echo "Compiling with g++..."
    g++ -O2 -Wall -fPIC -std=c++17 -I"$SCRIPT_DIR/include" "$SCRIPT_DIR/koverlay_mumble.cpp" -o "$TARGET_SO" -shared -lpthread
elif command -v clang++ >/dev/null 2>&1; then
    echo "Compiling with clang++..."
    clang++ -O2 -Wall -fPIC -std=c++17 -I"$SCRIPT_DIR/include" "$SCRIPT_DIR/koverlay_mumble.cpp" -o "$TARGET_SO" -shared -lpthread
elif [ -f "$SCRIPT_DIR/koverlay_mumble.so" ]; then
    echo "No C++ compiler found, but pre-compiled plugin exists. Using bundled binary..."
    cp -f "$SCRIPT_DIR/koverlay_mumble.so" "$TARGET_SO"
else
    echo "Error: Neither g++ nor clang++ was found. Please install a C++ compiler (e.g. 'sudo pacman -S gcc')."
    exit 1
fi

echo "=== Installing plugin to Mumble ==="
mkdir -p "$PLUGINS_DIR"
cp -f "$TARGET_SO" "$PLUGINS_DIR/koverlay_mumble.so"
chmod 755 "$PLUGINS_DIR/koverlay_mumble.so"

# If SCRIPT_DIR is writable (e.g. git development directory), also update the local copy
if [ -w "$SCRIPT_DIR" ]; then
    cp -f "$TARGET_SO" "$SCRIPT_DIR/koverlay_mumble.so" 2>/dev/null || true
fi

echo "Success! Plugin copied to: $PLUGINS_DIR/koverlay_mumble.so"
echo "Make sure to enable 'KOverlay Mumble Plugin' in Mumble under Configure -> Settings -> Plugins."
