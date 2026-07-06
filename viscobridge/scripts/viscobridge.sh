#!/usr/bin/env bash
# Launches ViscoBridge, creating a local virtualenv with the required
# dependencies on first run (subsequent runs reuse it).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$APP_DIR/.venv"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

cd "$APP_DIR"
exec "$VENV_DIR/bin/python" -m viscobridge "$@"
