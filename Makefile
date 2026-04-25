.PHONY: init scrape smoke stats clean dump shell \
        scrape-all scrape-loop scrape-kaidee scrape-toyotasure scrape-carcarrod scrape-one2car \
        schedule-install schedule-uninstall schedule-status schedule-tail

PLIST       := launchd/com.modz.car.scheduler.plist
PLIST_DEST  := $(HOME)/Library/LaunchAgents/com.modz.car.scheduler.plist

init:
	python3 db.py

# --- single-source scrapes ---
scrape:
	python3 scraper.py

scrape-kaidee:
	python3 scrape_all.py --only kaidee

scrape-toyotasure:
	python3 scrape_all.py --only toyotasure

scrape-carcarrod:
	python3 scrape_all.py --only carcarrod

scrape-one2car:
	python3 scrape_all.py --only one2car

# --- multi-source ---
scrape-all:
	python3 scrape_all.py --skip one2car        # one2car needs Playwright/cookie

scrape-loop:
	python3 scrape_all.py --loop 24h --jitter 30m --skip one2car

smoke:
	python3 scraper.py --smoke --note smoke

stats:
	python3 stats.py

shell:
	sqlite3 data/cars.db

dump:
	sqlite3 data/cars.db .dump > data/dump.sql
	@echo "wrote data/dump.sql"

# --- launchd ---
schedule-install: $(PLIST)
	@mkdir -p $(HOME)/Library/LaunchAgents
	cp $(PLIST) $(PLIST_DEST)
	launchctl unload $(PLIST_DEST) 2>/dev/null || true
	launchctl load   $(PLIST_DEST)
	@echo "installed: $(PLIST_DEST)"

schedule-uninstall:
	-launchctl unload $(PLIST_DEST) 2>/dev/null
	-rm -f $(PLIST_DEST)
	@echo "uninstalled"

schedule-status:
	@launchctl list | grep com.modz.car || echo "(not loaded)"

schedule-tail:
	tail -f data/scheduler.log data/scheduler.err

clean:
	rm -rf __pycache__ scrapers/__pycache__
