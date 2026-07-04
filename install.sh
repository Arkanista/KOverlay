#!/bin/bash

# KOverlay Universal Installer
set -e

echo "Starting KOverlay installation..."

# 1. Detect package manager and install dependencies
if command -v apt &> /dev/null; then
    echo "Detected apt (Debian/Ubuntu/Mint)..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip
elif command -v pacman &> /dev/null; then
    echo "Detected pacman (Arch/Manjaro/CachyOS)..."
    sudo pacman -Sy --needed python python-pip
elif command -v dnf &> /dev/null; then
    echo "Detected dnf (Fedora)..."
    sudo dnf install -y python3 python3-pip
elif command -v zypper &> /dev/null; then
    echo "Detected zypper (openSUSE)..."
    sudo zypper install -y python3 python3-pip
else
    echo "Unsupported package manager. Please install python3, python3-venv, and pip manually."
fi

# 2. Setup Python Virtual Environment
echo "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo "Activating virtual environment and installing requirements..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 3. Setup Desktop Integration
echo "Setting up Desktop Shortcut..."
mkdir -p ~/.local/share/icons/hicolor/scalable/apps/
mkdir -p ~/.local/share/applications/

# Copy icon
cp icon.svg ~/.local/share/icons/hicolor/scalable/apps/koverlay.svg

# Generate desktop file dynamically with absolute path
CURRENT_DIR=$(pwd)
cat > ~/.local/share/applications/koverlay.desktop << EOL
[Desktop Entry]
Version=0.1.0
Type=Application
Name=KOverlay
Comment=KOverlay TeamSpeak 3 Overlay
Exec="$CURRENT_DIR/start.sh"
Path=$CURRENT_DIR
Icon=koverlay
Terminal=false
Categories=Utility;Network;
EOL

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

echo "Installation complete! You can now launch KOverlay from your application menu."
