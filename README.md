# 🎮 HLTV Telegram Alert Bot

A Telegram bot that keeps you informed about the most important CS2 matches on [HLTV.org](https://www.hltv.org) and notifies you about your favorite teams.

## 🤖 Public Bot Instance

**You can use the bot right now without any installation!**
Start a chat with [@hltv_alert_bot](https://t.me/hltv_alert_bot) and send `/start`.

Or host your own instance using the instructions below.

## Features

- ✅ **Daily summary** – every morning (default 09:00) today's matches matching your star rating, plus all games of your favorite teams
- ✅ **Result notifications** – a message as soon as one of your favorite teams has finished a match
- ✅ **Star rating filter** – choose the minimum HLTV rating (1–5 ☆) for `/today` (last & next 24 h) and the summary
- ✅ **Favorite teams** – add/remove one or many teams at once, with spell-checking against the HLTV team list
- ✅ **Local times** – all match times are shown in your configured timezone
- ✅ **Responsive** – HLTV scraping runs in the background, the bot never freezes while loading
- ✅ **Gentle on HLTV** – rate-limited requests, a 30-minute match cache and a match snapshot on disk that survives restarts

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message; registers you for the daily summary |
| `/help` | Help and instructions |
| `/add [team]` | Add favorite team(s). Without a name the bot asks; separate several teams with commas or new lines |
| `/remove [team]` | Remove favorite team(s) (case-insensitive) |
| `/favorites` | Show your favorite teams |
| `/setminstar <1-5>` | Set the minimum star rating (default: 1) |
| `/today` | Results of the last 24 h, live matches and matches starting in the next 24 h, filtered by your star rating |
| `/favgames` | The next game of each favorite team |
| `/cancel` | Cancel the current `/add` or `/remove` dialog |

Commands are registered with Telegram automatically on startup, so they show up in the command menu.

### Example

```
/start
/setminstar 2
/add FaZe, Vitality, MOUZ
/today
/favgames
```

If a team name is ambiguous or misspelled, the bot rejects it and suggests matching teams (e.g. `/add faz` → *did you mean: FaZe, FaZe Academy?*).

## Installation

### Option 1: Docker (recommended) 🐳

Prerequisites: Docker with Docker Compose v2 (WSL2: Docker Desktop with WSL integration, see [docs/DOCKER.md](docs/DOCKER.md)).

```bash
git clone https://github.com/zGLados/hltv_telegram_alert.git
cd hltv_telegram_alert

cp .env.example .env
nano .env            # add your bot token from @BotFather

./docker.sh start    # build and start
./docker.sh logs -f  # follow logs
```

More commands (`stop`, `restart --pull`, `rebuild`, …) are described in [docs/DOCKER.md](docs/DOCKER.md).

### Option 2: Without Docker

Prerequisites: Python 3.12+.

```bash
git clone https://github.com/zGLados/hltv_telegram_alert.git
cd hltv_telegram_alert

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env            # add your bot token

./scripts/run_local.sh
```

### Creating a Telegram bot

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow the instructions
3. Copy the API token into `TELEGRAM_BOT_TOKEN` in `.env`

## Configuration

All settings are environment variables (read from `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | – (required) | Token from @BotFather |
| `TIMEZONE` | `Europe/Berlin` | Timezone for "today", the daily summary and displayed times |
| `DAILY_SUMMARY_TIME` | `09:00` | Time of the daily summary (`HH:MM`, in `TIMEZONE`) |
| `DATABASE_PATH` | `data/bot_data.db` | SQLite database file |
| `INITIAL_DATABASE_PATH` | `assets/initial_bot_data.db` | Template copied to `DATABASE_PATH` on first start |
| `MATCH_CACHE_FILE` | `match_cache.json` next to the DB | Snapshot of the last fetched match list |
| `SNAPSHOT_TIME` | `06:00` | Time of the daily match snapshot (`HH:MM`, in `TIMEZONE`) |

Scraper tuning (request delay, cache duration, max. match-page lookups) lives in `hltv_bot/config.py`.

### Star ratings

HLTV rates matches from 0 to 5 stars based on the teams' ranking:

| Stars | Meaning |
|-------|---------|
| 1 ☆ | Notable match (default filter) |
| 2 ☆☆ | Important match |
| 3 ☆☆☆ | High-profile match |
| 4–5 | Top-tier / big final matches |

## How it works

```
                ┌──────────────── bot.py ───────────────┐
 Telegram  ◄──► │ command handlers   scheduled jobs     │
                │        │                 │            │
                │        └── asyncio.to_thread ─┐       │
                └───────────────────────────────┼───────┘
                                                ▼
   database.py (SQLite)  ◄──────────  scraper.py ──► hltv.org
   users, favorites,                  rate-limited,
   notifications, teams               cached (curl_cffi)
                                            │
                                            ▼
                                   data/match_cache.json
                                   (match snapshot)
```

### Project structure

```
hltv_telegram_alert/
├── hltv_bot/                 # application package – start with: python -m hltv_bot
│   ├── __main__.py           #   entry point
│   ├── bot.py                #   Telegram handlers, scheduled jobs, startup
│   ├── scraper.py            #   HLTV fetching/parsing, rate limit, match snapshot
│   ├── database.py           #   SQLite: users, favorites, notifications, known teams
│   └── config.py             #   environment variables and scraper constants
├── assets/
│   └── initial_bot_data.db   # team-list template (~260 teams, no user data)
├── data/                     # runtime data, not in git (created automatically)
│   ├── bot_data.db           #   users and favorites
│   └── match_cache.json      #   match snapshot
├── tests/                    # pytest suite (runs offline)
├── docs/DOCKER.md            # Docker details and troubleshooting
├── scripts/run_local.sh      # start without Docker
├── docker.sh                 # Docker management (start, logs, restart --pull, …)
├── Dockerfile, docker-compose.yml
├── requirements.txt, requirements-dev.txt
└── .env.example              # configuration template
```

`bot.py` runs all blocking scraper calls in a worker thread so the bot stays responsive. `scraper.py` serialises and rate-limits every HLTV request (3 s) and mirrors the match list to the snapshot file.

### Scheduled jobs

| When | Job |
|------|-----|
| On startup | Load the match snapshot from disk, register commands, refresh match list and team list (in the background) |
| Every 30 min | Refresh the match list and look up kick-off times of rated matches |
| Every 30 min | Check results and notify fans of finished matches (each match only once) |
| `DAILY_SUMMARY_TIME` | Daily summary to every user who sent `/start` or has favorites |
| 03:00 | Refresh the team list from the HLTV ranking + current matches |
| 04:00 | Delete notification records older than 30 days |
| `SNAPSHOT_TIME` (06:00) | Daily match snapshot: fresh fetch, logs how many starred matches exist (e.g. `11 starred of 50 matches (1x ☆☆☆☆☆, …)`) |

### HTTP client

Requests to HLTV are made with [`curl_cffi`](https://github.com/lexiforest/curl_cffi) (`impersonate='chrome'`), which behaves like a regular browser. Keep its default headers – don't add a custom User-Agent to the session.

Requests are serialised with at least 3 seconds between them. A normal 30-minute refresh is a single request, because the match list already contains kick-off times.

### Match snapshot

Every successful fetch of the match list is written atomically to `data/match_cache.json` (fetch time, number of starred matches, all matches). On startup the bot loads it (dropping matches that started more than 6 hours ago), so it can answer immediately and still has data if HLTV is temporarily unreachable. The daily snapshot job at `SNAPSHOT_TIME` forces a fresh fetch shortly before the daily summary and logs a star breakdown.

### Parsing notes

- **Kick-off times** come from `data-unix` in the match list. If that ever disappears, the match page is fetched once per match and cached.
- **Live** means "kick-off has passed and the match is still listed". HLTV's `matchLive` CSS class is on *every* rating element and can't be used.
- **Event names** come from `data-event-headline`, with the URL slug as fallback.
- **TBD fixtures** (teams not yet known) are skipped.
- **Results**: the featured block at the top of `/results` has no timestamps and repeats matches; the timestamped main-list entry wins and untimed leftovers are dropped.

### Team validation

Team names you add are checked against the known-team list in the database:

1. exact match (case-insensitive) → `faze` becomes `FaZe`
2. otherwise a unique prefix → `vita` becomes `Vitality`
3. otherwise a unique substring → `equipa` becomes `BIG EQUIPA`
4. ambiguous or unknown input is rejected with suggestions

The list starts with the shipped template and is refreshed daily from HLTV. New teams are **merged** into the list; a failed or partial scrape never removes teams.

To update the template that new installations start with, copy the `valid_teams` table of a running instance into `assets/initial_bot_data.db` (it must contain no user data) and commit it:

```bash
sqlite3 assets/initial_bot_data.db "ATTACH 'data/bot_data.db' AS live;
  DELETE FROM valid_teams; INSERT INTO valid_teams SELECT * FROM live.valid_teams;"
git add assets/initial_bot_data.db && git commit -m "Update team template"
```

## Development

```bash
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests use small HTML snippets that mirror HLTV's markup, so they run offline. If HLTV changes its page structure, update the parser in `hltv_bot/scraper.py` together with the snippets in `tests/test_scraper.py`.

Changes are documented in [CHANGELOG.md](CHANGELOG.md).

## Troubleshooting

**Bot doesn't respond** – check the logs (`./docker.sh logs`), verify the token in `.env`, make sure you sent `/start`.

**"Team not found"** – use the name as shown on HLTV (e.g. `Natus Vincere`, `MOUZ`); the bot suggests similar names. If the list is empty, check the logs for team-refresh errors.

**No matches found** – check the logs for `Error fetching matches`. The bot keeps serving the last snapshot and retries every 30 minutes. If requests keep failing, try updating `curl_cffi`.

**Wrong times** – set `TIMEZONE` in `.env` and restart.

## Deployment notes

- `docker-compose.yml` uses `restart: unless-stopped`, so the bot comes back after reboots.
- Back up `data/bot_data.db` (users and favorites): `cp data/bot_data.db data/backup_$(date +%Y%m%d).db`
- Deploy updates with `./docker.sh restart --pull`.

<details>
<summary>systemd service (without Docker)</summary>

`/etc/systemd/system/hltv-bot.service`:

```ini
[Unit]
Description=HLTV Telegram Bot
After=network-online.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/hltv_telegram_alert
ExecStart=/path/to/hltv_telegram_alert/.venv/bin/python -m hltv_bot
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now hltv-bot
```
</details>

## License

MIT License

## Contributing

Pull requests are welcome! For major changes, please open an issue first. Please run the tests before submitting.

## Disclaimer

This bot is an unofficial project and is not affiliated with HLTV.org. Use it responsibly and don't overload HLTV's servers. If HLTV changes its website, fetching data may temporarily stop working.
