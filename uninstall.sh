#!/bin/bash

# KOverlay Universal Uninstaller
set -e

echo "Starting KOverlay uninstallation..."

echo "Stopping KOverlay if running..."
killall koverlay &> /dev/null || true

# 1. Remove Desktop Integration
echo "Removing Desktop Shortcut and Icons..."
rm -f ~/.local/share/applications/koverlay.desktop

for size in 16 32 48 64 128 256 512; do
    sudo rm -f "/usr/share/icons/hicolor/${size}x${size}/apps/koverlay.png"
done
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

# 2. Remove Application Files
INSTALL_DIR="$HOME/.local/share/koverlay"
echo "Removing Application Directory ($INSTALL_DIR)..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

echo "Uninstallation complete! The application has been removed from your system."
echo "Note: The configuration files in ~/.config/ts3-overlay/ were kept intact. If you want to delete them as well, run: rm -rf ~/.config/ts3-overlay"
