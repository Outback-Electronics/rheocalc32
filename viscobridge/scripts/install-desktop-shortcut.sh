#!/usr/bin/env bash
# Installs a ViscoBridge application-menu entry and (if present) a Desktop
# icon for the current user, on the Linux machine this is run on. The
# shortcut's Exec path is this checkout's absolute path, so re-run this
# script if you move or re-clone the repo elsewhere.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCHER="$SCRIPT_DIR/viscobridge.sh"
ICON="$APP_DIR/viscobridge/resources/icon.png"

chmod +x "$LAUNCHER"

DESKTOP_FILE_CONTENT="[Desktop Entry]
Type=Application
Name=ViscoBridge
Comment=Rotational viscometer/rheometer control and analysis
Exec=\"$LAUNCHER\"
Icon=$ICON
Path=$APP_DIR
Terminal=false
Categories=Science;Engineering;
StartupWMClass=ViscoBridge"

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
printf '%s\n' "$DESKTOP_FILE_CONTENT" > "$APPS_DIR/viscobridge.desktop"
chmod +x "$APPS_DIR/viscobridge.desktop"
echo "Installed application-menu entry: $APPS_DIR/viscobridge.desktop"

if [ -d "$HOME/Desktop" ]; then
    printf '%s\n' "$DESKTOP_FILE_CONTENT" > "$HOME/Desktop/viscobridge.desktop"
    chmod +x "$HOME/Desktop/viscobridge.desktop"
    # GNOME/Nautilus refuses to run an untrusted .desktop file on the
    # Desktop until this metadata flag is set (or the user right-clicks ->
    # Allow Launching); best-effort since gio isn't always installed.
    gio set "$HOME/Desktop/viscobridge.desktop" "metadata::trusted" true 2>/dev/null || true
    echo "Installed desktop icon: $HOME/Desktop/viscobridge.desktop"
fi

update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo "Done. ViscoBridge should now appear in your application menu (and on your Desktop if you have one)."
