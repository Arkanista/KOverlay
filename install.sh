#!/bin/bash

# KOverlay Universal Installer
set -e

echo "Starting KOverlay installation..."

# 1. Detect environment (Immutable Host vs Container vs Standard Distro)
IS_CONTAINER=0
if [ -f /run/.containerenv ] || [ -f /.dockerenv ] || [ -n "$CONTAINER_ID" ]; then
    IS_CONTAINER=1
fi

if [ "$IS_CONTAINER" -eq 0 ] && { [ -f /run/ostree-booted ] || command -v rpm-ostree &> /dev/null; }; then
    echo "Detected immutable ostree host (Bazzite / Fedora Atomic / Silverblue / Kinoite / SteamOS)..."
    echo "Skipping root filesystem package installation (installing entirely into ~/.local with isolated Python venv)."
    if command -v brew &> /dev/null && ! command -v mpv &> /dev/null; then
        echo "Tip: Using built-in system audio player (pw-play / paplay / gst-play-1.0). You can also optionally install mpv via: brew install mpv"
    fi
elif command -v apt &> /dev/null; then
    echo "Detected apt (Debian/Ubuntu/Mint/Pop!_OS)..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip mpv xdotool build-essential g++ libxcb-cursor0
elif command -v pacman &> /dev/null; then
    echo "Detected pacman (Arch/Manjaro/CachyOS/Garuda)..."
    sudo pacman -Sy --needed python python-pip python-pyqt6 qt6-svg mpv xdotool base-devel gcc
elif command -v dnf &> /dev/null; then
    echo "Detected dnf (Fedora/Nobara/Distrobox)..."
    sudo dnf install -y python3 python3-pip python3-pyqt6 qt6-qtsvg mpv xdotool gcc-c++ make xcb-util-cursor
elif command -v zypper &> /dev/null; then
    echo "Detected zypper (openSUSE)..."
    sudo zypper install -y python3 python3-pip mpv xdotool gcc-c++ make libxcb-cursor0
else
    echo "No standard mutable package manager detected. Proceeding with local user-space installation (~/.local)..."
fi

echo "Checking for window tracking tools..."
if [ -f "bin/kdotool" ]; then
    echo "Bundled kdotool available for KDE Plasma Wayland (active window tracking)."
elif command -v kdotool &> /dev/null; then
    echo "System kdotool found."
elif command -v xdotool &> /dev/null; then
    echo "System xdotool found."
else
    echo "Note: Neither kdotool nor xdotool was found. Active window tracking will be inactive until one is installed."
fi

# 2. Setup Application Directory
INSTALL_DIR="$HOME/.local/share/koverlay"
echo "Installing KOverlay to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy Python files, assets, and requirements
cp *.py "$INSTALL_DIR/"
cp icon.png "$INSTALL_DIR/"
if [ -f "icon.ico" ]; then
    cp icon.ico "$INSTALL_DIR/"
fi
if [ -f "LICENSE" ]; then
    cp LICENSE "$INSTALL_DIR/"
fi
cp requirements.txt "$INSTALL_DIR/"
if [ -d "icons" ]; then
    cp -r icons "$INSTALL_DIR/"
fi
if [ -d "bin" ]; then
    echo "Copying bundled binaries..."
    mkdir -p "$INSTALL_DIR/bin"
    cp -r bin/* "$INSTALL_DIR/bin/"
    chmod +x "$INSTALL_DIR/bin/"*
fi

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

echo "Installing icon sizes to ~/.local/share/icons/hicolor..."
for size in 16 32 48 64 128 256 512; do
    if [ -f "icons/koverlay-${size}.png" ]; then
        mkdir -p "$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
        cp "icons/koverlay-${size}.png" "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/koverlay.png"
        if [ ! -f /run/ostree-booted ] && [ -w /usr/share/icons ]; then
            sudo mkdir -p "/usr/share/icons/hicolor/${size}x${size}/apps" 2>/dev/null || true
            sudo cp "icons/koverlay-${size}.png" "/usr/share/icons/hicolor/${size}x${size}/apps/koverlay.png" 2>/dev/null || true
        fi
    fi
done
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
if [ ! -f /run/ostree-booted ] && [ -w /usr/share/icons ]; then
    sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

# 3. Setup Python Virtual Environment
echo "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv || python3 -m venv --system-site-packages venv
fi

# Generate start script
cat > start.sh << EOL
#!/bin/bash
cd "$INSTALL_DIR"
export PATH="\$PATH:$INSTALL_DIR/bin:\$HOME/.local/bin:/home/linuxbrew/.linuxbrew/bin:\$HOME/.linuxbrew/bin"
if [ -d "venv" ]; then
    exec ./venv/bin/python koverlay.py "\$@"
else
    exec python3 koverlay.py "\$@"
fi
EOL
chmod +x start.sh

echo "Activating virtual environment and installing requirements..."
source venv/bin/activate
pip install --upgrade pip 2>/dev/null || true
pip install -r requirements.txt
deactivate

# 4. Setup CLI Symlink and Desktop Integration
echo "Setting up ~/.local/bin/koverlay command and Desktop Shortcut..."
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/start.sh" "$HOME/.local/bin/koverlay"
mkdir -p ~/.local/share/applications/

# Generate desktop file dynamically with absolute path
cat > ~/.local/share/applications/koverlay.desktop << EOL
[Desktop Entry]
Version=1.5
Type=Application
Name=KOverlay
GenericName=Voice Overlay
Comment=Universal TeamSpeak 3, Mumble and Discord Overlay with TTS
Exec="$INSTALL_DIR/start.sh"
Path=$INSTALL_DIR
Icon=koverlay
Terminal=false
Categories=Utility;Network;Audio;
Keywords=teamspeak;ts3;mumble;discord;overlay;tts;eve;
EOL

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

echo "Installation complete! You can now launch KOverlay from your application menu."
