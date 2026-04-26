#!/usr/bin/env bash
# Push current main → server, rebuild, restart. Run from the laptop:
#
#   deploy/sync.sh                  # default host modz@204.168.243.132
#   CAR_HOST=user@host deploy/sync.sh
#
# Assumes:
#   * the server already has Car cloned at $REMOTE (default ~/Car)
#   * deploy/setup.sh has been run once
#   * git remote `origin` on the server is up-to-date with this branch

set -euo pipefail

HOST="${CAR_HOST:-modz@204.168.243.132}"
REMOTE="${CAR_REMOTE:-Car}"
BRANCH="${CAR_BRANCH:-main}"

echo "==> Sync $BRANCH → $HOST:$REMOTE"

ssh "$HOST" "set -e
  cd ~/$REMOTE
  git fetch origin --prune
  git checkout $BRANCH
  git reset --hard origin/$BRANCH

  # Reinstall any new Python deps (cheap when up-to-date)
  python3 -m pip install --user --break-system-packages --quiet \
      curl-cffi openai python-dotenv

  # Apply any schema migrations
  python3 -c 'from db import init; init()'

  # Rebuild Next.js bundle
  ~/.bun/bin/bun --cwd web install --frozen-lockfile
  ~/.bun/bin/bun --cwd web run build

  # Reload units in case anything in deploy/ changed, then restart web
  sudo cp deploy/car-web.service    /etc/systemd/system/
  sudo cp deploy/car-scrape.service /etc/systemd/system/
  sudo cp deploy/car-scrape.timer   /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl restart car-web.service
"

echo "==> Done. Tail logs with:"
echo "    ssh $HOST 'journalctl -u car-web -f'"
