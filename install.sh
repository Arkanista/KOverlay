#!/bin/bash

# KOverlay Universal Installer
set -e

echo "Starting KOverlay installation..."

# 1. Detect package manager and install dependencies
if command -v apt &> /dev/null; then
    echo "Detected apt (Debian/Ubuntu/Mint)..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip mpv xdotool build-essential g++
elif command -v pacman &> /dev/null; then
    echo "Detected pacman (Arch/Manjaro/CachyOS)..."
    sudo pacman -Sy --needed python python-pip mpv xdotool base-devel gcc
elif command -v dnf &> /dev/null; then
    echo "Detected dnf (Fedora)..."
    sudo dnf install -y python3 python3-pip mpv xdotool gcc-c++ make
elif command -v zypper &> /dev/null; then
    echo "Detected zypper (openSUSE)..."
    sudo zypper install -y python3 python3-pip mpv xdotool gcc-c++ make
else
    echo "Unsupported package manager. Please install python3, python3-venv, pip, mpv, and a C++ compiler manually."
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

# Copy Python files, assets, and requirements
cp *.py "$INSTALL_DIR/"
cp icon.png "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Copy Mumble plugin source and build files
if [ -d "mumble_plugin" ]; then
    echo "Copying Mumble plugin sources..."
    mkdir -p "$INSTALL_DIR/mumble_plugin"
    cp -r mumble_plugin/* "$INSTALL_DIR/mumble_plugin/"
    
    # Build and install Mumble plugin
    if [ -f "$INSTALL_DIR/mumble_plugin/build_and_install.sh" ]; then
        echo "Building and installing KOverlay Mumble Plugin..."
        bash "$INSTALL_DIR/mumble_plugin/build_and_install.sh" || echo "Warning: Mumble plugin build skipped (can be compiled later via Settings window)."
    fi
fi

echo "Installing icon sizes to /usr/share/icons/hicolor..."
for size in 16 32 48 64 128 256 512; do
    if [ -f "icons/koverlay-${size}.png" ]; then
        sudo mkdir -p "/usr/share/icons/hicolor/${size}x${size}/apps"
        sudo cp "icons/koverlay-${size}.png" "/usr/share/icons/hicolor/${size}x${size}/apps/koverlay.png"
    fi
done
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

# 3. Setup Python Virtual Environment
echo "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Generate start script
cat > start.sh << EOL
#!/bin/bash
cd "$INSTALL_DIR"
if [ -d "venv" ]; then
    exec ./venv/bin/python koverlay.py "\$@"
else
    exec python3 koverlay.py "\$@"
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
Version=1.5
Type=Application
Name=KOverlay
GenericName=Voice Overlay
Comment=Universal TeamSpeak 3 and Mumble Overlay with TTS
Exec="$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/koverlay.py"
Path=$INSTALL_DIR
Icon=koverlay
Terminal=false
Categories=Utility;Network;Audio;
Keywords=teamspeak;ts3;mumble;overlay;tts;eve;
EOL

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

echo "Installation complete! You can now launch KOverlay from your application menu."
