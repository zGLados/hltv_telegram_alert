# Changelog

## 2026-10-09 – Refactoring

### Fixed
- **Bot froze while scraping**: HLTV requests (incl. 3 s rate-limit sleeps and lazy match-page lookups) ran directly on the asyncio event loop, blocking all users. Scraping now runs in a worker thread.
- **Daily summary only reached users with favorites**, although `/start` promises it to everyone. Users are now registered on `/start`.
- **Team refresh destroyed the team list**: a successful scrape stored names in lowercase and *replaced* the list, so a partial scrape could wipe the 259 shipped teams. Teams are now merged and keep their capitalisation.
- **Times were shown as "UTC" but were container-local time**; "today" depended on the container's timezone. All times are timezone-aware and shown in `TIMEZONE`.
- Team names / user input were inserted into HTML messages unescaped (broken messages, possible formatting injection).
- Long messages could exceed Telegram's 4096-character limit.
- `/remove` was case-sensitive.
- Favorite matching used substrings (`BIG` matched `BIG EQUIPA`).
- `/add` picked an arbitrary team when the input matched several teams; it now asks with suggestions.
- Results were never filtered by age and the featured results block produced duplicates.
- Startup loaded teams and the match cache twice and delayed polling by up to a minute.
- Daily summary could be skipped silently if the job started > 1 s late (APScheduler misfire grace).
- `./docker.sh start --pull` pulled code but started the old image; `$CYAN` was undefined.
- `Accept-Encoding: zstd` was sent although `requests` can't decode it.

### Added
- `/today` shows a rolling window: results of the last 24 h, live matches (own section) and matches of the next 24 h, instead of the calendar day.
- Daily summary includes today's games of your favorite teams.
- "Did you mean …" suggestions for unknown team names.
- `/cancel` in the command menu, global error handler.
- Pruning of old notification records.
- pytest suite (`tests/`), `requirements-dev.txt`.
- Documentation: architecture, scheduled jobs, team validation, configuration table.

### Removed
- Dead code: unregistered `/alltoday`, unused date/time parsers, `get_matches_for_date`, inline-button handler.
- `start.sh` and `docker-check.sh` (superseded by `docker.sh`).
- Generated start script and file-exists healthcheck in the Dockerfile (DB template handling moved to `database.py`).
