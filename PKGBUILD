pkgname=koverlay
pkgver=1.1.1
pkgrel=1
pkgdesc="A modern, universal Wayland/X11 TeamSpeak 3, Mumble and Discord overlay with TTS voice announcements."
arch=('any')
url="https://github.com/Arkanista/KOverlay"
license=('GPL-3.0-or-later')
depends=('python' 'python-pyqt6' 'qt6-svg' 'kdotool' 'xdotool' 'mpv')
makedepends=('python-pip')
source=()

package() {
    # Create directories
    mkdir -p "$pkgdir/opt/koverlay"
    mkdir -p "$pkgdir/usr/bin"
    mkdir -p "$pkgdir/usr/share/applications"
    mkdir -p "$pkgdir/usr/share/licenses/$pkgname"
    # Install application files and icon
    cp -r "$startdir/"*.py "$pkgdir/opt/koverlay/"
    cp "$startdir/icon.png" "$pkgdir/opt/koverlay/icon.png"
    if [ -f "$startdir/LICENSE" ]; then
        cp "$startdir/LICENSE" "$pkgdir/opt/koverlay/LICENSE"
        install -Dm644 "$startdir/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    fi
    if [ -f "$startdir/icon.ico" ]; then
        cp "$startdir/icon.ico" "$pkgdir/opt/koverlay/icon.ico"
    fi
    if [ -d "$startdir/icons" ]; then
        cp -r "$startdir/icons" "$pkgdir/opt/koverlay/"
    fi

    if [ -d "$startdir/mumble_plugin" ]; then
        mkdir -p "$pkgdir/opt/koverlay/mumble_plugin"
        cp -r "$startdir/mumble_plugin/"* "$pkgdir/opt/koverlay/mumble_plugin/"
    fi
    
    for size in 16 32 48 64 128 256 512; do
        mkdir -p "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps"
        cp "$startdir/icons/koverlay-${size}.png" "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/koverlay.png"
    done

    # Install pip dependencies locally using --target
    pip install --target="$pkgdir/opt/koverlay/lib" ts3 edge-tts

    # Generate desktop file
    cat > "$pkgdir/usr/share/applications/koverlay.desktop" << EOF
[Desktop Entry]
Version=1.5
Type=Application
Name=KOverlay
GenericName=Voice Overlay
Comment=Universal TeamSpeak 3, Mumble and Discord Overlay with TTS
Exec=/usr/bin/koverlay
Icon=koverlay
Terminal=false
Categories=Utility;Network;Audio;
Keywords=teamspeak;ts3;mumble;discord;overlay;tts;eve;
EOF

    # Create wrapper executable
    cat > "$pkgdir/usr/bin/koverlay" << EOF
#!/bin/bash
export PYTHONPATH="/opt/koverlay/lib:\$PYTHONPATH"
cd /opt/koverlay || exit 1
exec python3 koverlay.py "\$@"
EOF
    chmod +x "$pkgdir/usr/bin/koverlay"
}
