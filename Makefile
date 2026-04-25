.PHONY: init scrape smoke stats clean dump shell

init:
	python3 db.py

scrape:
	python3 scraper.py

smoke:
	python3 scraper.py --smoke --note smoke

stats:
	python3 stats.py

shell:
	sqlite3 data/cars.db

dump:
	sqlite3 data/cars.db .dump > data/dump.sql
	@echo "wrote data/dump.sql"

clean:
	rm -rf __pycache__
