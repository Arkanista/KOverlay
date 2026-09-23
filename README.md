# <img src="icon.png" width="48" align="center"> KOverlay User Manual
> ✨ *Entirely vibecoded by Gemini 3.1 Pro AI agent* ✨

> [!TIP]
> **What's New in v0.1.15-1:**
> - 🎙️ **Full Mumble & TeamSpeak 3 Support**: Seamlessly switch between TS3 (ClientQuery) and Mumble (native C++ plugin with local IPC socket).
> - 🏷️ **Nickname Prefix & Tag Stripping**: Automatically remove clan brackets (`[...]`, `(...)`, `{...}`) and custom prefixes (e.g. `[VIP]`, `CLAN |`) for both overlay labels and TTS announcements.
> - 🔊 **Recent Speakers on Top & Fade**: Active speakers automatically jump to the top of the overlay, remaining highlighted with a customizable 0–60s fade-out timer.
> - 👥 **User List Limit**: Restrict the list of displayed users to a maximum count (X users).
> - ⚡ **Mumble Channel Filtering**: Fixed channel tracking so only users in your current channel are displayed.

Welcome to **KOverlay** – a powerful, modern overlay for Linux (X11 and Wayland) that integrates directly with **TeamSpeak 3** and **Mumble**, featuring voice announcements (TTS) of nicknames joining and leaving your channel! This step-by-step guide will explain how to configure the connection and what each option in the program menu does.

---

## Part 1: Installation & Requirements

KOverlay supports major Linux distributions natively and provides automated tools for deployment.

### Step 0: Clone the Repository
Before installing from source or using the installer script, clone the repository and navigate into it:
```bash
git clone https://github.com/Arkanista/KOverlay.git
cd KOverlay
```

Choose the appropriate installation method for your distribution below.

### Arch Linux / CachyOS / Manjaro / Garuda Linux

For Arch-based systems, an official `PKGBUILD` and a pre-compiled package are provided for clean system integration.

#### Method A: Build and Install from Source (Recommended)
Building from source automatically handles dependency resolution, including AUR packages:
1. Open a terminal in the cloned `koverlay` directory.
2. Build and install using the following commands:
   ```bash
   # Install dependencies from official repositories
   sudo pacman -S --needed python python-pyqt6 qt6-svg mpv xdotool
   
   # Install kdotool from the AUR (required for active window tracking on Wayland)
   yay -S kdotool   # or: paru -S kdotool
   
   # Build and install the koverlay package
   makepkg -si
   ```

#### Method B: Install the Pre-compiled Pacman Package
1. Download the pre-compiled package from GitHub releases:
   👉 **[Download KOverlay v0.1.15-1 (.pkg.tar.zst)](https://github.com/Arkanista/KOverlay/releases/download/v0.1.15-1/koverlay-0.1.15-1-any.pkg.tar.zst)**
2. **Important Note on Dependencies**: The package depends on `kdotool` (which is in the AUR). Standard `pacman` cannot automatically resolve or download AUR dependencies. You must install `kdotool` first:
   ```bash
   yay -S kdotool   # or: paru -S kdotool
   ```
3. Install the downloaded package:
   ```bash
   sudo pacman -U koverlay-0.1.15-1-any.pkg.tar.zst
   # Alternatively, let your AUR helper resolve dependencies and install the local package:
   yay -U koverlay-0.1.15-1-any.pkg.tar.zst
   ```

### Ubuntu / Debian / Linux Mint / Pop!_OS / Fedora / Nobara / openSUSE
For other distributions, a robust, universal installer script is provided:
1. Open a terminal in the KOverlay directory.
2. Run the installer: `./install.sh`
3. The script will automatically detect your package manager (`apt`, `dnf`, `zypper`), install Python and PIP dependencies into an isolated virtual environment (`venv`), and create a desktop shortcut.

> [!WARNING]
> **Active Window Tracking Limit (Wayland on Ubuntu/Debian):** 
> The feature "Show ONLY when game is active" requires either `xdotool` (for X11 displays) or `kdotool` (specifically for KDE Plasma Wayland). 
> 
> If you are using standard **Ubuntu with GNOME Wayland**, the display server strictly prevents apps from reading the active window. To use tracking on GNOME, you must log out and select **"Ubuntu on Xorg" (X11)**.
> 
> **How to install `kdotool` on Debian/Ubuntu (if using KDE Plasma Wayland):**
> Since Ubuntu/Debian do not have AUR, you can download the pre-compiled binary manually from the author's GitHub:
> ```bash
> wget https://github.com/jinliu/kdotool/releases/latest/download/kdotool-0.2.3-x86_64-unknown-linux-gnu.tar.gz
> tar -xzf kdotool-0.2.3-x86_64-unknown-linux-gnu.tar.gz
> sudo mv kdotool /usr/local/bin/
> sudo chmod +x /usr/local/bin/kdotool
> ```

### Bazzite / SteamOS / ChimeraOS (Immutable Systems)

Since Bazzite, SteamOS, ChimeraOS, and other immutable distributions use a read-only root filesystem, running the installer script `./install.sh` directly on the host will fail because directories like `/usr` are write-protected. The recommended way to run KOverlay on these systems is inside a **Distrobox** container (which is pre-installed on Bazzite and simple to set up on SteamOS/ChimeraOS).

> [!WARNING]
> **AI Generated Notice:** The following Bazzite/SteamOS/ChimeraOS container instructions were generated by an AI assistant and have not been physically tested on live installations. Use with caution.

1. Open your terminal.
2. Enter your default Distrobox container:
   ```bash
   distrobox enter
   ```
3. Navigate to the cloned `koverlay` folder inside the container and run the installation script:
   ```bash
   ./install.sh
   ```
4. Export the application to your Bazzite host menu so you can launch it like any native app:
   ```bash
   distrobox-export --app koverlay
   ```

### Uninstallation
To completely remove the application and its shortcuts from your system, simply run `./uninstall.sh`. To clear user settings, delete the `~/.config/ts3-overlay/` folder.

---

## Part 2: How to connect KOverlay to TeamSpeak 3

## Part 2: How to Connect (TeamSpeak 3 & Mumble)

KOverlay supports two distinct voice backends: **TeamSpeak 3** and **Mumble**. You can switch between them anytime in the **Settings** window under **Voice Backend**.

### Option A: Connecting to TeamSpeak 3 (ClientQuery)
KOverlay talks directly to your running TeamSpeak 3 application via the built-in **ClientQuery** plugin:
1. Open **TeamSpeak 3** -> `Tools` -> `Options` -> `Addons`.
2. Locate **ClientQuery** and ensure it is **Enabled**.
3. Open its Settings / API Key and copy your key.
4. In KOverlay Settings, select backend **TeamSpeak 3** and paste your API key into the `TS3 API Key:` field.

### Option B: Connecting to Mumble (Native Plugin)
KOverlay connects to Mumble via a high-performance native plugin and a local IPC socket:
1. Compile and install the plugin (already included in the Pacman package or installed via `./mumble_plugin/build_and_install.sh`).
2. Open **Mumble** -> `Configure` -> `Settings` -> `Plugins`.
3. Check and enable **KOverlay Mumble Plugin**.
4. In KOverlay Settings, select backend **Mumble** (IPC port `25640` by default). KOverlay will automatically filter the channel and display speaking statuses in real time!

---

## Part 3: Full Description of Features and Settings

The *Settings* window offers highly advanced overlay customization. All options are saved in real-time and updated immediately on the screen, without the need to click a "Save" button.

### Voice Backend & Connection
*   **Voice Backend (TS3 / Mumble):** Switch the active voice client on the fly.
*   **TS3 API Key / Mumble Port:** Authorization and port settings for the respective clients.
*   **Target Window Keywords:** Allows you to define window titles KOverlay looks for to detect when the target game is active (e.g., `EVE - `, `exefile.exe`, `Steam`).
*   **Show ONLY when game is active:** Automatically hides the overlay when you alt-tab out of the game.
*   **Delay hiding when game loses focus:** Configurable grace period (1–60s) before hiding the overlay when switching windows.

### User List & Speaking Behavior
*   **Move recent speakers to top of list:** When enabled, users who talk immediately move to the top of the overlay.
*   **Keep recent speakers highlighted (Fade duration):** Slider from 0 to 60 seconds. Provides a smooth color fade transition back to regular text color after someone stops speaking.
*   **Limit user list:** Option to restrict the list to the top `X` active users.
*   **Remove all bracket tags ([...], (...), {...}):** Strips leading tag brackets from player names (e.g. `[CORP] Player` -> `Player`).
*   **Nick Prefixes...:** Opens a dedicated dialog to configure custom prefix strings to strip (e.g. `[VIP]`, `CLAN |`, etc.) from both overlay labels and TTS announcements.

### Overlays Section
*   **Enable Overlay 1 - 4:** KOverlay's architecture allows you to launch up to **four clones** of the overlay. This feature is dedicated to players operating on multiple monitors simultaneously. By checking the respective boxes, you "wake up" the corresponding display identifiers (IDs). For each awakened "ID", the system independently remembers its screen coordinates, allowing you to precisely assign Overlay 2 to the second monitor and Overlay 3 to the third.

### Features
- Displays the current TeamSpeak 3 channel.
- Shows a list of users who are currently speaking (along with a 10-second history of joins/leaves).
- Configurable opacity and a hotkey (default `Shift+Tab`) to show/hide the window containing the event history, including join and leave notifications.
- Integration with the system TTS engine (Edge TTS) to read out join and leave notifications.
- **TTS Aliases (Substitution List)**: Ability to substitute hard-to-pronounce nicknames or remove clan tags so the TTS engine reads them correctly.
- GUI for settings (sliders for TTS volume, window opacity) - accessible from the tray icon.

### Width Settings Section
*   **Dynamic Width (fit to text):** Automatic corset. The window naturally reacts to what's happening inside it. If you have people with short nicknames on the channel, the window stays extremely narrow. It only expands wider when a person with a long nickname enters.
*   **Fixed Width:** Manual frame. If you uncheck *Dynamic Width*, the *Fixed* slider activates. It allows you to impose an absolute, rock-solid width in pixels on the program (from 50px to 1000px). Regardless of the length of the players' nicknames, the frame will strictly stick to this dimension. This prevents the UI layout from "jumping" around.

### Background & Colors Section
*   **Background Opacity (Normal Mode):** Controls the opacity of the base overlay tiles (the "glass") while playing. Pulling the slider to *0%* removes the virtual window box – leaving only the dry letters of the nicknames floating phenomenally over the game itself.
*   **Background Opacity (Move Mode):** The opacity value imposed exclusively when manual positioning mode is enabled (see tray menu). The optimal approach is to crank this value up while arranging the overlay, to more clearly draw the edges of the window you need to grab with the mouse.
*   **Choose Background Color:** The primary color of the frame/background window. Supports alpha transparency (you can choose the tint of the glass frame).
*   **Choose Text Color (Normal):** Imposes the selected color on the letters identifying the nickname of a player who is currently on the channel with you, but is silent and not transmitting voice.
*   **Choose Text Color (Talking):** Speaker highlight. This defines the intense color that a player's nickname entry will "flash" when they press their push-to-talk button or activate their microphone via voice activation in TS3.
*   **Choose Text Color (Left):** Ghost highlight. Defines the color for users who have recently left the channel but are still displayed on the screen due to the "History Duration" setting.

### Typography Section
*   **Font / Size:** Standard system font picker. Allows you to swap the overlay font and set its absolute size (e.g., 11, 14, or increase to 20 for 4K resolution monitors).

### Visual Options Section
*   **Show Title Header (Logo + Text):** Official overlay header. Adds a distinct visual program logo and a text identifier (e.g., "KOverlay - ID 1") to the frame. Keeps the window looking like a classic software block.
*   **Show Dots Indicator:** Highly compact mode. If you disable the *Title Header*, you can enable the "Dots Indicator". This makes the text header disappear, leaving only tiny, LED-like dots (`•••`) at the very top of the frame. The number of dots displayed corresponds to the identification number of that display clone (1 dot = Overlay ID 1). The footprint is minimized to physical zero, and the dotted line is small enough not to interfere with the game, while serving as the only available drag-handle for the mouse when arranging the element on the screen!
*   **Disable border blinking on startup:** By default, KOverlay "blinks" its outer border in an aggressive red color upon invocation (for a 5-second cycle). This functionality was implemented so that the player, amidst cluttered screens, can instantly visually locate where the hidden transparent window spawned. This option permanently disables the blinking signal – maximizing minimalism.

### Join/Leave History Section
*   **Enable Join/Leave History (+ / ✝ indicators):** When enabled, KOverlay tracks the presence of users. New users joining the channel will be prefixed with a bold `+ ` for a specified duration. Users who leave the channel will stay on the list for the specified duration but will be pushed to the bottom, prefixed with a `✝ ` symbol, and colored gray (or a custom color of your choice). This allows you to know who just entered or left without looking at the TS3 window!
*   **History Duration:** Defines how long (in seconds) the new/left users keep their visual indicators before fading away (left users) or turning into regular users (new users).

### Text-to-Speech (TTS) Section
*   **Enable Text-to-Speech (TTS):** Text-to-Speech integration! When enabled, whenever someone joins or leaves the channel, a natural AI voice from Microsoft Azure will announce their arrival/departure out loud. 
    * *Requires active internet connection for the high-quality voice.*
    * *Requires the `edge-tts` python module and the `mpv` video player to be installed on your Linux system. (These are installed automatically via our universal installers).*
*   **TTS Voice / Language:** Allows you to select the voice persona. Currently supports highly realistic voices: **English Female (Aria)** and **Polish Female (Zofia)**. You can easily test how they sound by clicking the "Test" button!
*   **TTS Speed Control:** Adjust the reading speed from `-50%` to `+100%`. Fast speeds are perfectly supported!
*   **TTS Phrase for Join / Leave:** Allows you to completely customize what the voice says. Use the special variable `%NICK` to place the user's name in the sentence. For example, typing `%NICK arrived on the battlefield` will cause the bot to say exactly that!
*   **Read Delay:** Defines a delay (up to 3 seconds) before the TTS voice speaks, preventing overlaps with standard TS3 joining sounds.
*   **Volume:** Slider to independently control the loudness of the TTS announcements (0% to 100%).
*   **TTS Queueing:** Announcements are safely queued and played seamlessly one after another without overlapping. We use hardware-accelerated silence removal to ensure perfect, gapless playback when multiple people join at once!
*   **TTS Persistent Cache:** KOverlay smartly caches generated speech files locally in a human-readable format to avoid unnecessary network calls. You can view the cache size, open the cache folder, clear it manually, or configure the **Auto-clear** feature to automatically delete audio files older than a specified number of days.

---

## Part 4: System Tray Interface (Move Mode)

**Right-Clicking** the icon in the bottom-right corner of the system tray (next to the system clock) opens the KOverlay menu with two critical operational entries (aside from accessing settings):

1. **Move Overlays (Checkbox):** 
   * Launches "Rearrangement" mode when checked.
   * Normally, the overlay ignores all clicks (the cursor passes through it to the game below) so you don't accidentally click it during gameplay!
   * Activating this option freezes mouse communication with the game beneath the window frame, colors the KOverlay frame into a visible dashed line, and applies the "Move Mode" opacity.
   * In this mode, simply grab any of the enabled windows with the Left Mouse Button and move it freely to any corner of the monitor.
   * **To lock the positions**, simply uncheck `Move Overlays` in the tray menu. The overlays will instantly freeze, hide the auxiliary dashed edges, and resume ignoring mouse strikes, passing control directly back to the game client!
   * > [!NOTE]
   * > **Automatic Move Mode:** Opening the **Settings** window from the tray menu will also automatically force all active overlays into "Move Mode" for as long as the settings window remains open. Closing the settings window will revert the overlays to their previous locked state.

2. **Mute TTS Voice (Checkbox):**
   * A quick toggle switch. Checking this option will instantly mute all voice announcements without changing your master settings. Perfect for temporarily silencing the bot without having to open the full Settings panel!
