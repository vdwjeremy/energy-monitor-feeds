#!/bin/sh
set -eu

INSTALL_DIR=/opt/energy-monitor-feeds
CONFIG_DIR=/etc/energy-monitor-feeds
SERVICE_USER=energy-feed
SERVICE_GROUP=energy-feed
UNIT_NAME=energy-feed@.service
COLLECTORS='weather_api refoss_em06 ds18b20 yf_b10'

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [ "$(id -u)" -ne 0 ]; then
    fail "run this script with sudo from $INSTALL_DIR"
fi

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
REPO_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
if [ "$REPO_DIR" != "$INSTALL_DIR" ]; then
    fail "expected the checkout at $INSTALL_DIR (found $REPO_DIR)"
fi

for required_file in pyproject.toml config/config.example.toml deploy/systemd/energy-feed@.service; do
    [ -f "$REPO_DIR/$required_file" ] || fail "missing $REPO_DIR/$required_file"
done

command -v python3 >/dev/null 2>&1 || fail "python3 is required"
command -v systemctl >/dev/null 2>&1 || fail "systemctl is required"

PYTHON_VERSION=$(python3 -c 'import sys; print("%d %d" % sys.version_info[:2])') || fail "could not run python3"
PYTHON_MAJOR=${PYTHON_VERSION%% *}
PYTHON_MINOR=${PYTHON_VERSION#* }
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]; }; then
    fail "Python 3.9 or newer is required"
fi

for collector in "$@"; do
    case " $COLLECTORS " in
        *" $collector "*) ;;
        *) fail "unknown collector '$collector'; choose from: $COLLECTORS" ;;
    esac
    if [ "$collector" = refoss_em06 ] && { [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; }; then
        fail "Refoss requires Python 3.11 or newer"
    fi
done

if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
    groupadd --system "$SERVICE_GROUP"
fi
if ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_GROUP" --no-create-home --home-dir /nonexistent "$SERVICE_USER"
    usermod -a -G gpio $SERVICE_USER
fi

install -d -o root -g "$SERVICE_GROUP" -m 0750 "$CONFIG_DIR"
if [ ! -e "$CONFIG_DIR/config.toml" ]; then
    install -o root -g "$SERVICE_GROUP" -m 0640 \
        "$REPO_DIR/config/config.example.toml" "$CONFIG_DIR/config.toml"
fi
if [ ! -e "$CONFIG_DIR/energy-feed.env" ]; then
    install -o root -g "$SERVICE_GROUP" -m 0640 /dev/null "$CONFIG_DIR/energy-feed.env"
fi

if [ ! -x "$INSTALL_DIR/.venv/bin/python" ]; then
    python3 -m venv "$INSTALL_DIR/.venv" || fail "could not create the virtual environment; install python3-venv"
fi
"$INSTALL_DIR/.venv/bin/python" -m pip install "$INSTALL_DIR"

install -o root -g root -m 0644 \
    "$REPO_DIR/deploy/systemd/$UNIT_NAME" "/etc/systemd/system/$UNIT_NAME"
systemctl daemon-reload

if [ "$#" -gt 0 ]; then
    for collector in "$@"; do
        systemctl enable --now "energy-feed@$collector"
    done
else
    printf 'Installation complete. Services were not enabled or started.\n'
    printf 'Review %s/config.toml and %s/energy-feed.env, then pass collector names to enable them.\n' \
        "$CONFIG_DIR" "$CONFIG_DIR"
fi