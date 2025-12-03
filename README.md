# 🎮 HLTV Telegram Alert Bot

A Telegram bot that keeps you informed about the most important CS:GO/CS2 matches on HLTV.org and sends notifications about your favorite teams.

## Features

✅ **Daily Match Overview** - Get a morning summary of the most important matches of the day  
✅ **Manage Favorite Teams** - Add your favorite teams and receive notifications  
✅ **Live Results** - Automatic updates when your favorite teams' matches end  
✅ **Star Filter** - Only important matches (based on HLTV star rating)  
✅ **Easy to Use** - Intuitive commands for management

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
   ./docker-start.sh
   ```
   
   Or manually:
   ```bash
   docker compose up --build -d
   ```

5. **View Logs**
   ```bash
   docker compose logs -f
   ```

6. **Stop Bot**
   ```bash
   docker compose down
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
| `/today` | Shows today's most important matches |
| `/alltoday` | Shows ALL matches for today (no star filter) |
| `/games` | Shows next match for each favorite team |
| `/favorites` | Shows your favorite teams |
| `/add` | Add a favorite team |
| `/remove` | Remove a favorite team |

### Example Workflow

1. Start the bot with `/start`
2. Add your favorite teams:
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
3. Check today's matches:
   ```
   /today
   ```
4. The bot automatically sends:
   - Daily summary at 09:00 AM
   - Notifications about your favorites' matches
   - Results after matches end

## Configuration

In `config.py` you can adjust the following settings:

- `MIN_STARS_FOR_IMPORTANT`: Minimum number of stars for "important" matches (default: 1)
- `DAILY_SUMMARY_TIME`: Time for daily summary (default: 09:00)
- `TIMEZONE`: Timezone for notifications (default: Europe/Berlin)

## Automatic Notifications

The bot checks:
- **Daily at 09:00 AM**: Sends a summary of all important matches
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
├── bot.py              # Main file with bot logic
├── hltv_scraper.py    # HLTV.org scraper
├── database.py        # SQLite database management
├── config.py          # Configuration
└── requirements.txt   # Python dependencies
```

### Technologies Used

- **python-telegram-bot** - Telegram Bot API
- **cloudscraper** - Bypassing Cloudflare protection on HLTV
- **BeautifulSoup4** - Web scraping and HTML parsing
- **APScheduler** - Scheduled tasks (daily summaries, cache refresh)
- **SQLite** - Database for user favorites and notification tracking

## Troubleshooting

### Bot doesn't respond

1. Check if the bot is running: `python bot.py`
2. Verify the token in the `.env` file
3. Make sure you've started a conversation with the bot in Telegram (`/start`)

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

The bot is already running as a Docker container if you used `./start.sh` or `docker compose up -d`.

**Useful Commands:**

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