#!/usr/bin/env bash
# One-time server setup for Car. Run on the Hetzner box as the user that
# will own the deployment (e.g. `modz`):
#
#   bash deploy/setup.sh
#
# Idempotent — safe to re-run.

set -euo pipefail

CAR_HOME="${CAR_HOME:-$HOME/Car}"

echo "==> Car setup at $CAR_HOME"

# 1. Pre-reqs: assume system already has python3, git, sqlite3, caddy.
#    bun ships in $HOME/.bun if you've already deployed Indicator there.
command -v python3   >/dev/null || { echo "install python3 first"; exit 1; }
command -v sqlite3   >/dev/null || { echo "install sqlite3 first";  exit 1; }
command -v "$HOME/.bun/bin/bun" >/dev/null || {
  echo "bun not found at $HOME/.bun/bin/bun — install with"
  echo "  curl -fsSL https://bun.sh/install | bash"
  exit 1
}

# 2. Python deps. Use --user --break-system-packages to mirror dev.
echo "==> Installing Python deps"
python3 -m pip install --user --break-system-packages --quiet \
    curl-cffi openai python-dotenv

# 3. Optional: Playwright for one2car (heavy — only if you plan to scrape it)
if [ "${INSTALL_PLAYWRIGHT:-0}" = "1" ]; then
  python3 -m pip install --user --break-system-packages --quiet \
      playwright playwright-stealth
  python3 -m playwright install chromium
fi

# 4. Initialise the SQLite (idempotent)
echo "==> Initialising DB schema"
cd "$CAR_HOME"
python3 -c "from db import init; init()"

# 5. Build the Next.js bundle
echo "==> Building Next.js"
"$HOME/.bun/bin/bun" --cwd "$CAR_HOME/web" install --frozen-lockfile
"$HOME/.bun/bin/bun" --cwd "$CAR_HOME/web" run build

# 6. systemd units (require sudo)
echo "==> Installing systemd units (needs sudo)"
sudo cp "$CAR_HOME/deploy/car-web.service"    /etc/systemd/system/
sudo cp "$CAR_HOME/deploy/car-scrape.service" /etc/systemd/system/
sudo cp "$CAR_HOME/deploy/car-scrape.timer"   /etc/systemd/system/

# Substitute the user/path placeholders if not modz/$HOME
ME="${USER}"
if [ "$ME" != "modz" ] || [ "$CAR_HOME" != "/home/modz/Car" ]; then
  echo "==> Patching systemd units for user=$ME, home=$CAR_HOME"
  sudo sed -i "s|/home/modz/Car|$CAR_HOME|g; s|User=modz|User=$ME|g; s|Group=modz|Group=$ME|g" \
      /etc/systemd/system/car-web.service \
      /etc/systemd/system/car-scrape.service
fi

sudo systemctl daemon-reload
sudo systemctl enable --now car-web.service
sudo systemctl enable --now car-scrape.timer

echo "==> Done"
echo "    Web:   http://localhost:3344  (point Caddy at it — see Caddyfile.snippet)"
echo "    Timer: $(sudo systemctl list-timers car-scrape.timer --no-pager | tail -2 | head -1)"
echo "    Logs:  journalctl -u car-web -f"
echo "           journalctl -u car-scrape -f"
