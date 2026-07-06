#!/usr/bin/env bash
# Launches ViscoBridge with the system python3 -- the same interpreter/
# environment you'd use running `python -m viscobridge` from a terminal.
# No virtualenv: dependencies must already be installed
# (pip install -r requirements.txt) for whichever python3 is on PATH.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${TMPDIR:-/tmp}/viscobridge-launch.log"

cd "$APP_DIR"
python3 -m viscobridge "$@" >"$LOG_FILE" 2>&1
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    # Terminal=false means a double-click launch has no visible output, so
    # a failure here would otherwise look like "nothing happened" -- show
    # it with whatever dialog tool is available instead.
    ERROR_MSG="ViscoBridge failed to start (exit code $STATUS).

Log: $LOG_FILE

$(tail -n 20 "$LOG_FILE")"
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --title="ViscoBridge failed to start" --width=500 --text="$ERROR_MSG"
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --title "ViscoBridge failed to start" --error "$ERROR_MSG"
    elif command -v xmessage >/dev/null 2>&1; then
        xmessage -center "$ERROR_MSG"
    fi
fi

exit "$STATUS"
