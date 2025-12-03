# 🎮 HLTV Telegram Alert Bot

A Telegram bot that keeps you informed about the most important CS:GO/CS2 matches on HLTV.org and sends notifications about your favorite teams.

## 🤖 Public Bot Instance

**You can use the bot right now without any installation!**

Simply start a chat with [@hltv_alert_bot](https://t.me/hltv_alert_bot) on Telegram and send `/start` to begin.

**Or host your own instance using the instructions below.**

## Features

✅ **Daily Match Overview** - Get a morning summary at 9:00 AM with matches based on your star rating preference  
✅ **Customizable Star Rating** - Set your preferred minimum star rating (1-3 stars) to filter matches  
✅ **Manage Favorite Teams** - Add your favorite teams and see their upcoming games  
✅ **Auto-updating Commands** - Bot commands are automatically registered via Telegram API  
✅ **Smart Caching** - 30-minute cache system for improved performance  
✅ **Clean Format** - Matches displayed with clickable links to HLTV match pages

## Installation

### Option 1: With Docker (Recommended) 🐳

**Prerequisites:**
- Docker and Docker Compose installed
- For WSL2 users: Docker Desktop with WSL2 integration enabled

**Steps:**

1. **Clone Repository**
   ```bash
   git clone https://github.com/zGLados/hltv_telegram_alert.git
   cd hltv_telegram_alert
   ```

2. **Create Telegram Bot**
   - Open Telegram and search for [@BotFather](https://t.me/BotFather)
   - Send `/newbot` and follow the instructions
   - Copy the API token

3. **Configuration**
   ```bash
   cp .env.example .env
   nano .env  # or use any text editor
   ```
   Enter your bot token:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TIMEZONE=Europe/Berlin
   DAILY_SUMMARY_TIME=09:00
   ```

4. **Start Bot**
   ```bash
   ./docker.sh start
   ```
   
   Or manually:
   ```bash
   docker compose up --build -d
   ```

5. **View Logs**
   ```bash
   ./docker.sh logs
   # or with follow mode:
   ./docker.sh logs -f
   ```

6. **Stop Bot**
   ```bash
   ./docker.sh stop
   ```

For detailed Docker instructions and troubleshooting, see [DOCKER.md](DOCKER.md)

### Option 2: Without Docker

**Prerequisites:**
- Python 3.12 or higher

**Steps:**

### 1. Clone Repository

```bash
git clone https://github.com/zGLados/hltv_telegram_alert.git
cd hltv_telegram_alert
```

### 2. Set up Python Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the API token you receive

### 5. Configuration

Create a `.env` file in the project directory:

```bash
cp .env.example .env
```

Edit the `.env` file and add your bot token:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TIMEZONE=Europe/Berlin
DAILY_SUMMARY_TIME=09:00
```

## Usage

### Start Bot

```bash
python bot.py
```

The bot is now running and accessible via Telegram!

### Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and overview |
| `/help` | Help and instructions |
| `/add` | Add a favorite team |
| `/remove` | Remove a favorite team |
| `/favorites` | Shows your favorite teams |
| `/setminstar <number>` | Set minimum star rating (1-5) |
| `/today` | Shows today's important matches (based on your star rating) |
| `/favgames` | Shows next match for each favorite team |

### Example Workflow

1. Start the bot with `/start`
2. Set your preferred star rating (optional, default is 1):
   ```
   /setminstar 2
   ```
3. Add your favorite teams:
   ```
   /add FaZe
   ```
   Or use bulk add:
   ```
   /add
   FaZe
   BIG
   Vitality
   done
   ```
4. Check today's matches:
   ```
   /today
   ```
5. Check your favorite teams' upcoming games:
   ```
   /favgames
   ```
6. The bot automatically sends:
   - Daily summary at 09:00 AM (respecting your star rating setting)
   - Shows matches with clickable links to HLTV

## Configuration

In `config.py` you can adjust the following settings:

- `DAILY_SUMMARY_TIME`: Time for daily summary (default: 09:00)
- `TIMEZONE`: Timezone for notifications (default: Europe/Berlin)

### User Settings (per user)

Each user can customize:
- **Minimum Star Rating**: Set via `/setminstar` command (default: 1)
  - 1 star: Important matches
  - 2 stars: Very important matches
  - 3 stars: High-profile matches
  - 4 stars: Top-tier matches
  - 5 stars: Elite/Major matches

## Automatic Notifications

The bot checks:
- **Daily at 09:00 AM**: Sends a summary of important matches (respecting your star rating)
- **Every 30 minutes**: Checks if your favorite teams' matches have ended and refreshes match cache

### Smart Caching System

The bot uses an intelligent caching system to ensure fast responses and accurate data:
- Match data is cached for 30 minutes
- Match dates/times are fetched directly from HLTV match pages for accuracy
- Cache is automatically refreshed every 30 minutes
- Important matches (1+ stars) have their dates pre-loaded during cache refresh

## Technical Details

### Architecture

```
├── bot.py                    # Main file with bot logic
├── hltv_scraper.py          # HLTV.org scraper
├── database.py              # SQLite database management
├── config.py                # Configuration
├── init_db_with_teams.py    # Script to initialize database with teams
├── requirements.txt         # Python dependencies
└── data/
    ├── initial_bot_data.db  # Pre-loaded database with 259 teams
    └── bot_data.db          # Runtime database (created automatically)
```

### Technologies Used

- **python-telegram-bot** - Telegram Bot API
- **cloudscraper** - Bypassing Cloudflare protection on HLTV
- **BeautifulSoup4** - Web scraping and HTML parsing
- **APScheduler** - Scheduled tasks (daily summaries, cache refresh)
- **SQLite** - Database for user favorites, notification tracking, and team validation

### Team Validation

The bot includes a database with 259 CS:GO/CS2 teams from HLTV rankings. When you add a team:
- Team names are validated against the database (case-insensitive)
- Correct capitalization is automatically applied (e.g., `flyquest` → `FlyQuest`)
- Teams are updated daily from HLTV (when accessible)
- Initial database is included in the repository for immediate use

**Updating the Team Database:**

If you want to update the team list with current HLTV rankings:

1. **Download HLTV Rankings Page:**
   - Visit https://www.hltv.org/ranking/teams in your browser
   - Right-click → "Save page as..." → Save as HTML
   - Save as `Counter-Strike Ranking _ World Ranking _ HLTV.org.htm` in project root

2. **Run Update Script:**
   ```bash
   python3 init_db_with_teams.py
   ```
   This creates a fresh `data/initial_bot_data.db` with all teams from the HTML file.

3. **Commit Updated Database:**
   ```bash
   git add data/initial_bot_data.db
   git commit -m "Update team database to current HLTV rankings"
   ```

**Note:** This is only needed when you want to update the template database for all users. The bot automatically attempts to update teams daily from HLTV, but due to Cloudflare protection this often fails. The pre-loaded database ensures all 259 teams work immediately.

## Troubleshooting

### Bot doesn't respond

1. Check if the bot is running: `python bot.py`
2. Verify the token in the `.env` file
3. Make sure you've started a conversation with the bot in Telegram (`/start`)

### Team not found

- Check spelling - team names must match HLTV rankings
- The database contains 259 teams from HLTV's world rankings
- Use `/add teamname` with common names like: FaZe, Navi, G2, Vitality, BIG, MOUZ, M80, FlyQuest
- If HLTV scraping is blocked, the bot uses the pre-loaded team database

### No matches found

- HLTV.org might be temporarily unavailable
- Check your internet connection
- There might be no important matches today
- **Note:** HLTV.org uses aggressive anti-scraping protection, so matches may not be available

### Notifications not arriving

- Make sure you've added favorites (`/favorites`)
- Check the timezone in the `.env` file
- Verify your favorite teams are playing today

## Deployment

### Docker (Production Environment)

The bot is already running as a Docker container if you used `./docker.sh start` or `docker compose up -d`.

**Docker Management Script:**

The `docker.sh` script provides easy container management:

```bash
# Start bot
./docker.sh start

# Start bot and pull latest changes from git first
./docker.sh start --pull

# Stop bot
./docker.sh stop

# Restart bot (quick restart without rebuild)
./docker.sh restart

# Restart bot and pull latest changes (git pull + rebuild + restart)
./docker.sh restart --pull

# Rebuild bot (full rebuild without git pull)
./docker.sh rebuild

# View logs
./docker.sh logs

# View logs with follow mode
./docker.sh logs -f

# Check status
./docker.sh status
```

**Manual Docker Commands:**

```bash
# Check status
docker compose ps

# View logs
docker compose logs -f

# Restart bot
docker compose restart

# Stop bot
docker compose down

# Rebuild container
docker compose up --build -d

# Enter container (for debugging)
docker compose exec hltv-bot /bin/bash
```

### Systemd Service (without Docker)

Create `/etc/systemd/system/hltv-bot.service`:

```ini
[Unit]
Description=HLTV Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/hltv_telegram_alert
Environment="PATH=/path/to/hltv_telegram_alert/.venv/bin"
ExecStart=/path/to/hltv_telegram_alert/.venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable hltv-bot
sudo systemctl start hltv-bot
```

### Server Deployment with Docker

For a production server, it's recommended to:

1. **Automatic start after reboot:**
   
   The `docker-compose.yml` already uses `restart: unless-stopped`

2. **Database backup:**
   ```bash
   # Create backup
   docker compose exec hltv-bot cp /app/data/bot_data.db /app/data/backup_$(date +%Y%m%d).db
   
   # Or from host
   cp data/bot_data.db data/backup_$(date +%Y%m%d).db
   ```

3. **Deploy updates:**
   ```bash
   # Using docker.sh (automatically pulls git changes and rebuilds)
   ./docker.sh restart --pull
   
   # Or manually
   git pull
   docker compose down
   docker compose up --build -d
   ```

4. **Monitoring:**
   ```bash
   # Resource usage
   docker stats hltv-telegram-bot
   
   # Last hour's logs
   docker compose logs --since 1h
   ```

### With Docker Swarm or Kubernetes

For Swarm:
```bash
docker stack deploy -c docker-compose.yml hltv-bot
```

For Kubernetes, you can use the Docker images and create appropriate deployments.

### With Docker (manually without Compose)

```bash
# Build image
docker build -t hltv-bot .

# Start container
docker run -d \
  --name hltv-telegram-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  hltv-bot

# View logs
docker logs -f hltv-telegram-bot

# Stop
docker stop hltv-telegram-bot
docker rm hltv-telegram-bot
```

## License

MIT License

## Contributing

Pull requests are welcome! For major changes, please open an issue first.

## Disclaimer

This bot is an unofficial project and is not affiliated with HLTV.org. Use it responsibly and don't overload HLTV.org servers. **Please note:** HLTV.org uses aggressive anti-scraping protection (Cloudflare), so automatic match fetching may not always work reliably.