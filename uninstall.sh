#!/bin/bash

# KOverlay Universal Uninstaller
set -e

echo "Starting KOverlay uninstallation..."

# 1. Remove Desktop Integration
echo "Removing Desktop Shortcut and Icon..."
rm -f ~/.local/share/applications/koverlay.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/koverlay.svg

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/
fi

# 2. Remove Python Virtual Environment
echo "Removing Python virtual environment..."
if [ -d "venv" ]; then
    rm -rf venv
fi

echo "Uninstallation complete! The application has been removed from your system menu."
echo "Note: The configuration files in ~/.config/ts3-overlay/ were kept intact. If you want to delete them as well, run: rm -rf ~/.config/ts3-overlay"
