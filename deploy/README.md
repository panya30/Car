# Deploying Car

Native deployment on a Hetzner box — same shape as Indicator (systemd +
Caddy + bun, no Docker, no Vercel). Three units, one shared SQLite, one
Caddy site.

```
            ┌─────────────────────────────────────────────────┐
            │ Hetzner box (e.g. 204.168.243.132)              │
            │                                                 │
   :443 ──► │  Caddy (TLS) ──► :3344 car-web.service (Next)   │
            │                       │                         │
            │                       └── reads ──┐             │
            │                                   ▼             │
            │                            data/cars.db ◄──┐    │
            │                                            │    │
            │  car-scrape.timer  (daily 03:30 + jitter)──┘    │
            │     │                                           │
            │     └── triggers car-scrape.service             │
            │           └── python scrape_all.py              │
            │                  └── pipeline.py (matches,      │
            │                      stories, photos, LINE)     │
            └─────────────────────────────────────────────────┘
```

## First deploy

1. **DNS**: point an A record to your Hetzner IP. e.g. `car.indicator.live`.

2. **SSH onto the box** and clone:
   ```bash
   ssh modz@204.168.243.132
   cd ~ && git clone https://github.com/panya30/Car.git
   ```

3. **Mirror your `.env`** from local (it's gitignored):
   ```bash
   # Locally:
   scp Car/.env modz@204.168.243.132:~/Car/.env
   ```

4. **Run setup**:
   ```bash
   cd ~/Car && bash deploy/setup.sh
   ```
   This installs Python deps, initialises the schema, builds the Next.js
   bundle, copies the three systemd units, and starts the web service +
   the daily timer.

5. **Add the Caddy site**. Open `/etc/caddy/Caddyfile`, append the block
   from `deploy/Caddyfile.snippet` (replacing `car.example.com` with your
   real subdomain), then:
   ```bash
   sudo systemctl reload caddy
   ```

6. **First scrape** — don't wait until 03:30 tomorrow:
   ```bash
   sudo systemctl start car-scrape.service   # one-shot
   journalctl -u car-scrape -f                # watch progress
   ```

7. **Visit https://car.example.com**.

## Subsequent deploys

From your laptop:

```bash
git push                       # push to GitHub main
deploy/sync.sh                 # fetch on server, rebuild, restart web
# or:  CAR_HOST=user@host deploy/sync.sh
```

`sync.sh` is idempotent and applies any schema migrations
(`from db import init`) safely. It does not touch the timer.

## Daily ops

| Question | Command |
|---|---|
| Is the next scrape scheduled? | `systemctl list-timers car-scrape.timer` |
| Watch tonight's run live | `journalctl -u car-scrape -f` |
| Trigger an extra scrape now | `sudo systemctl start car-scrape.service` |
| Web logs | `journalctl -u car-web -f` |
| Web status | `systemctl status car-web` |
| Restart web | `sudo systemctl restart car-web` |
| Open the DB | `sqlite3 ~/Car/data/cars.db` |

## Pipeline knobs

The timer runs `scrape_all.py --skip one2car --sleep 4 --sleep-taladrod 8`
which in turn invokes `pipeline.py` (cross-source matches → stories →
photos → LINE). Edit `deploy/car-scrape.service` and re-sync to change.

To enable one2car, install Playwright on the server:
```bash
INSTALL_PLAYWRIGHT=1 bash deploy/setup.sh
# then remove `--skip one2car` from car-scrape.service
```

## Backups

The SQLite is the only state. WAL is on, so you can hot-copy:

```bash
# Local backup snapshot (keeps a week of nightly copies)
mkdir -p ~/backups
sqlite3 ~/Car/data/cars.db ".backup ~/backups/cars-$(date +%Y%m%d).db"
find ~/backups -name 'cars-*.db' -mtime +7 -delete
```

A simple weekly `cron` line is enough for now:
```cron
0 4 * * * sqlite3 /home/modz/Car/data/cars.db ".backup /home/modz/backups/cars-$(date +\%Y\%m\%d).db"
```

## Secrets

`Car/.env` (gitignored) holds:
- `OPENAI_API_KEY` — used by photo_verify + llm_polish
- `LINE_CHANNEL_ACCESS_TOKEN` + `LINE_TARGET_USER_ID` — optional, for
  pushing alerts to LINE
- `CF_CLEARANCE` — optional, lets the curl-cffi path fetch one2car for
  ~30 min after you paste it

`scrapers/_common.py` auto-loads this file via `python-dotenv`, so neither
the systemd service nor your shell needs to export anything.
