# <img src="icon.png" width="48" align="center"> KOverlay User Manual
> ✨ *Entirely vibecoded by Gemini 3.1 Pro AI agent* ✨

Welcome to **KOverlay** – a powerful, modern overlay for Linux (X11 and Wayland) that integrates directly with TeamSpeak 3, featuring voice announcements (TTS) of nicknames joining your channel! This step-by-step guide will explain how to configure the connection and what each option in the program menu does.

---

## Part 1: Installation & Requirements

KOverlay supports major Linux distributions natively and provides automated tools for deployment.

### Arch Linux / CachyOS / Manjaro
For Arch-based systems, an official `PKGBUILD` and a compiled package are provided for clean system integration:
1. Open a terminal in the KOverlay directory.
2. Build the package: `makepkg -si`
   *(This will automatically fetch required dependencies like `python-pyqt6` and the AUR package `kdotool`).*
3. Or download and install the pre-compiled package directly via terminal: 
   `sudo pacman -U https://github.com/Arkanista/koverlay/releases/download/v0.1.10/koverlay-0.1.10-10-any.pkg.tar.zst`
4. **[Direct Download Link]** You can also download the package manually through your browser: 
   👉 **[Download KOverlay v0.1.10-10 (.pkg.tar.zst)](https://github.com/Arkanista/koverlay/releases/download/v0.1.10/koverlay-0.1.10-10-any.pkg.tar.zst)**

### Ubuntu / Debian / Linux Mint / Fedora / openSUSE
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
> chmod +x /usr/local/bin/kdotool
> ```

### Uninstallation
To completely remove the application and its shortcuts from your system, simply run `./uninstall.sh`. To clear user settings, delete the `~/.config/ts3-overlay/` folder.

---

## Part 2: How to connect KOverlay to TeamSpeak 3

KOverlay does not connect to voice servers in the cloud – it "talks" directly to your running TeamSpeak 3 application via a special built-in TS3 plugin called **ClientQuery**.

To establish this connection, follow these steps:

### Step 1: Enable the ClientQuery Plugin in TS3
1. Open **TeamSpeak 3**.
2. From the top menu bar, select `Tools`, then `Options`.
3. On the left side of the Options window, select the `Addons` tab.
4. Scroll through the list (or use the search bar in the top-left) to find a plugin named **ClientQuery**.
5. Ensure that the plugin is **Enabled**.

### Step 2: Copy the API Key
1. Double-click the enabled **ClientQuery** plugin (or click the 'Settings' button below it).
2. In the small plugin configuration window, you will find a text field labeled **API Key**.
3. If the field is empty, generate a new key by clicking the button next to it.
4. **Copy** this string of characters to your clipboard (Ctrl+C) – this is the unique password that allows local data reading!

### Step 3: Launch KOverlay and Paste the Key
1. Launch the KOverlay application (e.g., by running the `./start.sh` file in the program directory).
2. You will see a new circular blue icon with sound waves in your **System Tray** (the taskbar area next to the clock).
3. Right-click the KOverlay icon and select **Settings**.
4. At the very top of the window, you will find a field: `TS3 API Key:`.
5. Paste the copied key from your clipboard (Ctrl+V) into this field.

The key is saved **automatically on the fly**. From now on, KOverlay is fully connected! All you have to do is connect to any server and join a channel in TS3, and the overlays will come to life, displaying the list of participants in the room.

---

## Part 3: Full Description of Features and Settings

The *Settings* window offers highly advanced overlay customization. All options are saved in real-time and updated immediately on the screen, without the need to click a "Save" button.

### Authorization and Game Section
*   **TS3 API Key:** The unique authorization token from the ClientQuery plugin, described above. Essential for the program to function.
*   **Show ONLY when game is active:** If this option is checked, KOverlay will automatically monitor the system. The overlay will only appear when your target game/application window is on top and has focus. If you switch to a web browser or minimize the game, the window will discreetly disappear.
*   **Target Window Keywords:** Allows you to define exactly what window names KOverlay should look for when deciding if the target game/application is active. By default, it looks for `EVE - ` or `exefile.exe`, but you can enter a comma-separated list of any keywords. This prevents the overlay from incorrectly activating when you browse a forum in your web browser.
*   **Delay hiding when game loses focus:** Extends the above feature. If you alt-tab to a second monitor or another app, the overlay will stay visible for a configurable number of seconds (1 to 60) before fading away. If you return to the game within this time, the overlay remains visible continuously.

### Overlays Section
*   **Enable Overlay 1 - 4:** KOverlay's architecture allows you to launch up to **four clones** of the overlay. This feature is dedicated to players operating on multiple monitors simultaneously. By checking the respective boxes, you "wake up" the corresponding display identifiers (IDs). For each awakened "ID", the system independently remembers its screen coordinates, allowing you to precisely assign Overlay 2 to the second monitor and Overlay 3 to the third.

### Width Settings Section
*   **Dynamic Width (fit to text):** Automatic corset. The window naturally reacts to what's happening inside it. If you have people with short nicknames on the channel, the window stays extremely narrow. It only expands wider when a person with a long nickname enters.
*   **Fixed Width:** Manual frame. If you uncheck *Dynamic Width*, the *Fixed* slider activates. It allows you to impose an absolute, rock-solid width in pixels on the program (from 50px to 1000px). Regardless of the length of the players' nicknames, the frame will strictly stick to this dimension. This prevents the UI layout from "jumping" around.

### Background & Colors Section
*   **Background Opacity (Normal Mode):** Controls the opacity of the base overlay tiles (the "glass") while playing. Pulling the slider to *0%* removes the virtual window box – leaving only the dry letters of the nicknames floating phenomenally over the game itself.
*   **Background Opacity (Move Mode):** The opacity value imposed exclusively when manual positioning mode is enabled (see tray menu). The optimal approach is to crank this value up while arranging the overlay, to more clearly draw the edges of the window you need to grab with the mouse.
*   **Choose Background Color:** The primary color of the frame/background window. Supports alpha transparency (you can choose the tint of the glass frame).
*   **Choose Text Color (Normal):** Imposes the selected color on the letters identifying the nickname of a player who is currently on the channel with you, but is silent and not transmitting voice.
*   **Choose Text Color (Talking):** Speaker highlight. This defines the intense color that a player's nickname entry will "flash" when they press their push-to-talk button or activate their microphone via voice activation in TS3.

### Typography Section
*   **Font / Size:** Standard system font picker. Allows you to swap the overlay font and set its absolute size (e.g., 11, 14, or increase to 20 for 4K resolution monitors).

### Visual Options Section
*   **Show Title Header (Logo + Text):** Official overlay header. Adds a distinct visual program logo and a text identifier (e.g., "KOverlay - ID 1") to the frame. Keeps the window looking like a classic software block.
*   **Show Dots Indicator:** Highly compact mode. If you disable the *Title Header*, you can enable the "Dots Indicator". This makes the text header disappear, leaving only tiny, LED-like dots (`•••`) at the very top of the frame. The number of dots displayed corresponds to the identification number of that display clone (1 dot = Overlay ID 1). The footprint is minimized to physical zero, and the dotted line is small enough not to interfere with the game, while serving as the only available drag-handle for the mouse when arranging the element on the screen!
*   **Disable border blinking on startup:** By default, KOverlay "blinks" its outer border in an aggressive red color upon invocation (for a 5-second cycle). This functionality was implemented so that the player, amidst cluttered screens, can instantly visually locate where the hidden transparent window spawned. This option permanently disables the blinking signal – maximizing minimalism.

### Join/Leave History & TTS Voice
*   **Enable Join/Leave History (+ / ✝ indicators):** When enabled, KOverlay tracks the presence of users. New users joining the channel will be prefixed with a bold `+ ` for a specified duration. Users who leave the channel will stay on the list for the specified duration but will be pushed to the bottom, prefixed with a `✝ ` symbol, and colored gray (or a custom color of your choice). This allows you to know who just entered or left without looking at the TS3 window!
*   **History Duration:** Defines how long (in seconds) the new/left users keep their visual indicators before fading away (left users) or turning into regular users (new users).
*   **Enable TTS Voice Announcements (English):** Text-to-Speech integration! When enabled, whenever someone joins the channel, a natural AI voice (AriaNeural from Microsoft Azure) will announce their arrival out loud (e.g., "Arkanis joined"). 
    * *Requires active internet connection for the high-quality voice.*
    * *Requires the `edge-tts` python module and the `mpv` video player to be installed on your Linux system. (These are installed automatically via our universal installers).*
*   **Read Delay:** Defines a delay (up to 3 seconds) before the TTS voice speaks, preventing overlaps with standard TS3 joining sounds.
*   **Volume:** Slider to independently control the loudness of the TTS announcements (0% to 100%).

---

## Part 4: System Tray Interface (Move Mode)

**Right-Clicking** the icon in the bottom-right corner of the system tray (next to the system clock) opens the KOverlay menu with two critical operational entries (aside from accessing settings):

1. **Move Overlays:** 
   * Launches "Rearrangement" mode.
   * Normally, the overlay ignores all clicks (the cursor passes through it to the game below) so you don't accidentally click it during gameplay!
   * Activating this option freezes mouse communication with the game beneath the window frame, colors the KOverlay frame into a visible dashed line, and applies the "Move Mode" opacity.
   * In this mode, simply grab any of the enabled windows with the Left Mouse Button and move it freely to any corner of the monitor. **Releasing the left mouse button immediately hard-saves the new coordinate.**

2. **Mute TTS Voice:**
   * A quick toggle switch. Checking this option will instantly mute all voice announcements without changing your master settings. Perfect for temporarily silencing the bot without having to open the full Settings panel!

3. **Lock Positions:**
   * Exits "Rearrangement" mode.
   * The `Move Overlays` button automatically changes its label to `Lock Positions` while moving. Click it once you've finished arranging the frame, and the overlays will instantly freeze, hide the auxiliary dashed edges, and resume ignoring mouse strikes, passing control directly back to the game client!
