# CLAUDE.md

Project context for Claude Code. User-facing docs live in README.md, docs/DOCKER.md and CHANGELOG.md – keep them in sync with code changes.

## What this is

Telegram bot (python-telegram-bot 20, asyncio) that scrapes HLTV.org for CS2 matches: `/today` (results of the last 24 h, live, next 24 h, filtered by the user's min. star rating), favorite teams, a daily summary and "match finished" notifications. SQLite for state, APScheduler for jobs, Docker for deployment.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest              # tests (offline, ~1 s)
.venv/bin/python -m pyflakes hltv_bot tests
.venv/bin/python -m hltv_bot            # run the bot (needs TELEGRAM_BOT_TOKEN in .env)
./docker.sh start | logs -f | restart --pull | rebuild
```

CI (`.github/workflows/ci.yml`) runs pyflakes + pytest and a Docker build/smoke test on every push to `main`. Keep it green.

## Layout

- `hltv_bot/bot.py` – handlers, scheduled jobs, startup (`post_init`). Blocking helpers (`fetch_window`, `fetch_next_games`, `fetch_summary_matches`, `refresh_match_cache`, `daily_snapshot`) are module-level functions called via `asyncio.to_thread`.
- `hltv_bot/scraper.py` – `HLTVScraper` + `Match` dataclass; parsing is in static/class methods (`parse_matches_page`, `parse_results_page`) so tests can feed HTML directly.
- `hltv_bot/database.py` – `Database` (SQLite, one connection per call).
- `hltv_bot/config.py` – env vars + scraper constants.
- `assets/initial_bot_data.db` – team-list template (no user data), copied to `DATABASE_PATH` on first start.
- `data/` – runtime only (bot_data.db, match_cache.json), gitignored. Never commit anything from it.

## Rules that matter

- **Never block the event loop.** Anything that touches HLTV must run through `asyncio.to_thread`. SQLite calls are fine on the loop.
- **All HLTV requests go through `HLTVScraper._get`** (lock + 3 s rate limit). It uses `curl_cffi` with `impersonate='chrome'`; plain `requests`/`cloudscraper`/`curl` get HTTP 403. Do not set custom headers (User-Agent etc.) on the session.
- **Escape everything in HTML messages** (`html.escape` for team/event names and user input) and send long text via `reply_html` / `_send`, which split at Telegram's 4096-char limit on blank lines (one block = one match).
- **Team list only grows**: `update_valid_teams` merges and keeps capitalisation; never replace/delete teams on a partial scrape.
- **Favorites match exactly** (case-insensitive) – `Match.has_team` must not use substrings (`BIG` ≠ `BIG EQUIPA`).
- Times are timezone-aware UTC internally; display via `Match.local_time` (config `TZ`).

## HLTV markup quirks (verified against the live site, Oct 2026)

- `/matches`: containers are `div.match`; teams in `div.match-teamname`; kick-off in `[data-unix]` (ms); event in `[data-event-headline]`; stars = non-`faded` `i.fa-star` inside `div.match-rating`. Containers without team names are TBD fixtures → skipped. Duplicates exist → dedupe by match id.
- `matchLive` is on **every** rating element → useless. Live = kick-off passed and still listed (`Match.is_live`).
- `/results`: `div.result-con` with `data-zonedgrouping-entry-unix`; the featured block at the top has no timestamps and repeats matches → the timestamped entry wins, untimed leftovers are dropped.
- `/ranking/teams` redirects to the current weekly ranking; names in `div.ranked-team span.name`.
- If parsing breaks, fetch the page with curl_cffi, inspect, then update parser **and** the HTML snippets in `tests/test_scraper.py`.

## Conventions

- Code, comments, docs, commit messages and bot texts in English.
- Every user-visible change gets a CHANGELOG.md entry; update README/docs when behaviour, commands, config or paths change.
- Pin dependencies to exact versions that are at least ~2 weeks old.
- Tests must stay offline: feed HTML snippets / monkeypatch `scraper._get`; use a temp DB.
- Commit in logical steps with descriptive messages; `main` is what gets deployed (`./docker.sh restart --pull`).
