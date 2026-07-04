pkgname=koverlay
pkgver=0.1.8
pkgrel=1
pkgdesc="A modern, universal Wayland/X11 TeamSpeak 3 overlay."
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
    mkdir -p "$pkgdir/usr/share/icons/hicolor/scalable/apps"

    # In a real PKGBUILD, we would copy from $srcdir. Since this is local, we copy from the current directory.
    # Note: When building locally with makepkg, you might need to adjust paths if the source is not packaged.
    cp -r "$startdir/"*.py "$pkgdir/opt/koverlay/"
    cp "$startdir/icon.svg" "$pkgdir/usr/share/icons/hicolor/scalable/apps/koverlay.svg"
    cp "$startdir/icon.svg" "$pkgdir/opt/koverlay/icon.svg"

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
Icon=/usr/share/icons/hicolor/scalable/apps/koverlay.svg
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
