# Wytyczne i reguły projektu (KOverlay)

## Skrypt instalacyjny i pliki wdrożeniowe
- **Zawsze po wprowadzeniu zmian w projekcie** (np. dodanie nowych plików źródłowych, zasobów, modułów, zmian w `requirements.txt`, zależnościach systemowych lub strukturze katalogów):
  - Sprawdź skrypt instalacyjny ([install.sh](file:///home/arkanis/TS%20Overlay/install.sh)).
  - Sprawdź, czy nie wymaga on aktualizacji (kopiowanie nowych plików/zasobów, instalacja nowych pakietów/zależności, uprawnienia, skrypt deinstalacyjny [uninstall.sh](file:///home/arkanis/TS%20Overlay/uninstall.sh) lub [PKGBUILD](file:///home/arkanis/TS%20Overlay/PKGBUILD)).
  - Wprowadź wszystkie niezbędne poprawki, aby proces instalacji zawsze działał bezbłędnie z najnowszą wersją aplikacji.

## Budowanie paczek i wydania (GitHub Actions)
- **Zawsze buduj paczki na GitHubie** za pomocą workflow [build.yml](file:///home/robert/TS%20Overlay/.github/workflows/build.yml) (Arch `.pkg.tar.zst`, Debian/Ubuntu `.deb`, Fedora/Bazzite `.rpm`, `AppImage`, `Flatpak`, Windows `KOverlay_Setup.exe` i `KOverlay_Portable.zip`), zamiast polegać wyłącznie na ręcznym budowaniu lokalnym.
- **Zawsze po wygenerowaniu paczek podłączaj je do odpowiedniego taga / release'u** na GitHubie (`v<pkgver>`).
