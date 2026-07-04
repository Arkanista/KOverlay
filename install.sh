#!/bin/bash

# KOverlay Universal Installer
set -e

echo "Starting KOverlay installation..."

# 1. Detect package manager and install dependencies
if command -v apt &> /dev/null; then
    echo "Detected apt (Debian/Ubuntu/Mint)..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip mpv
elif command -v pacman &> /dev/null; then
    echo "Detected pacman (Arch/Manjaro/CachyOS)..."
    sudo pacman -Sy --needed python python-pip mpv
elif command -v dnf &> /dev/null; then
    echo "Detected dnf (Fedora)..."
    sudo dnf install -y python3 python3-pip mpv
elif command -v zypper &> /dev/null; then
    echo "Detected zypper (openSUSE)..."
    sudo zypper install -y python3 python3-pip mpv
else
    echo "Unsupported package manager. Please install python3, python3-venv, pip, and mpv manually."
fi

echo "Checking for required window tracking tools..."
if ! command -v kdotool &> /dev/null && ! command -v xdotool &> /dev/null; then
    echo "CRITICAL ERROR: 'kdotool' (Wayland) or 'xdotool' (X11) is strictly required."
    
    if command -v yay &> /dev/null; then
        echo "Attempting to install kdotool from AUR using yay..."
        yay -Sy --needed kdotool || exit 1
    elif command -v paru &> /dev/null; then
        echo "Attempting to install kdotool from AUR using paru..."
        paru -Sy --needed kdotool || exit 1
    else
        echo "Please install 'kdotool' (from AUR) or 'xdotool' manually to continue."
        exit 1
    fi
fi

# 2. Setup Application Directory
INSTALL_DIR="$HOME/.local/share/koverlay"
echo "Installing KOverlay to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy necessary files
cp *.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"
cp icon.svg "$INSTALL_DIR/"
# Note: start.sh is no longer needed as we use the venv directly in the desktop file

# 3. Setup Python Virtual Environment
echo "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Generate start script
cat > start.sh << EOL
#!/bin/bash
cd $INSTALL_DIR
# Use venv python if exists
if [ -d "venv" ]; then
    exec ./venv/bin/python koverlay.py
else
    exec python3 koverlay.py
fi
EOL
chmod +x start.sh

echo "Activating virtual environment and installing requirements..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 4. Setup Desktop Integration
echo "Setting up Desktop Shortcut..."
mkdir -p ~/.local/share/applications/

# Generate desktop file dynamically with absolute path
cat > ~/.local/share/applications/koverlay.desktop << EOL
[Desktop Entry]
Version=0.1.8
Type=Application
Name=KOverlay
Comment=KOverlay - TS3 Overlay
Exec="$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/koverlay.py"
Path=$INSTALL_DIR
Icon=$INSTALL_DIR/icon.svg
Terminal=false
Categories=Utility;Network;
EOL

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

echo "Installation complete! You can now launch KOverlay from your application menu."
