pkgname=koverlay
pkgver=0.1.10
pkgrel=9
pkgdesc="A modern, universal Wayland/X11 TeamSpeak 3 overlay with TTS voice announcements."
arch=('any')
url="https://github.com/arkanis/koverlay" # Replace with actual URL if known
license=('GPL')
depends=('python' 'python-pyqt6' 'qt6-svg' 'kdotool' 'xdotool' 'mpv')
makedepends=('python-pip')
source=()

package() {
    # Create directories
    mkdir -p "$pkgdir/opt/koverlay"
    mkdir -p "$pkgdir/usr/bin"
    mkdir -p "$pkgdir/usr/share/applications"
    # Install application files and icon
    cp -r "$startdir/"*.py "$pkgdir/opt/koverlay/"
    cp "$startdir/icon.png" "$pkgdir/opt/koverlay/icon.png"
    
    for size in 16 32 48 64 128 256 512; do
        mkdir -p "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps"
        cp "$startdir/icons/koverlay-${size}.png" "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/koverlay.png"
    done

    # Install pip dependencies locally using --target
    pip install --target="$pkgdir/opt/koverlay/lib" ts3 edge-tts

    # Generate desktop file
    cat > "$pkgdir/usr/share/applications/koverlay.desktop" << EOF
[Desktop Entry]
Version=$pkgver
Type=Application
Name=KOverlay
Comment=KOverlay TeamSpeak 3 Overlay
Exec=/usr/bin/koverlay
Icon=/opt/koverlay/icon.png
Terminal=false
Categories=Utility;Network;
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
