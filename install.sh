#!/bin/sh
#
# codegraph-piggyback bootstrap installer.
#
# Clones (or updates) this repo into a stable location, then runs
# `piggyback install` — which installs stock codegraph if absent, reconciles
# your global hooks, and drops a `piggyback` launcher on PATH.
#
#   curl -fsSL https://raw.githubusercontent.com/<YOUR_GH_USER>/codegraph-piggyback/main/install.sh | sh
#
# Uninstall:  piggyback uninstall   (then: rm -rf ~/.codegraph-piggyback)
#
# Env:
#   PIGGYBACK_REPO        owner/repo slug   (default below)
#   PIGGYBACK_INSTALL_DIR clone location    (default: ~/.codegraph-piggyback)
set -eu

# >>> EDIT THIS to your fork's slug, or export PIGGYBACK_REPO before running. <<<
REPO="${PIGGYBACK_REPO:-YOUR_GH_USER/codegraph-piggyback}"
DIR="${PIGGYBACK_INSTALL_DIR:-$HOME/.codegraph-piggyback}"
URL="https://github.com/${REPO}.git"

if ! command -v git >/dev/null 2>&1; then
  echo "piggyback: git is required but not installed." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "piggyback: python3 is required but not installed." >&2
  exit 1
fi

if [ -d "$DIR/.git" ]; then
  echo "piggyback: updating existing checkout in $DIR"
  git -C "$DIR" pull --ff-only
else
  echo "piggyback: cloning $URL → $DIR"
  git clone "$URL" "$DIR"
fi

# install: codegraph (if absent) + global hooks + launcher. Skip the in-CLI
# self-update — we just pulled.
python3 "$DIR/piggyback.py" install --no-update

cat <<EOF

piggyback installed.
  - Restart your agent session so Claude Code loads the new hooks.
  - Ensure ~/.local/bin is on PATH so the 'piggyback' command works.
  - Per repo:  piggyback init
EOF
