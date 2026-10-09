# Docker Setup for HLTV Telegram Bot

## Prerequisites

### Enable Docker Desktop WSL2 Integration

1. **Open Docker Desktop**
2. Go to **Settings** (⚙️) → **Resources** → **WSL Integration**
3. Enable **"Enable integration with my default WSL distro"**
4. Also enable your specific WSL2 distribution (e.g., Ubuntu)
5. Click **"Apply & Restart"**
6. Wait until Docker Desktop has restarted

### Alternative: Docker without WSL Integration

If you don't want to integrate Docker Desktop with WSL, you can run Docker commands directly from Windows PowerShell.

## Setup

1. **Configure environment variables:**
   ```bash
   cp .env.example .env
   nano .env  # Add your bot token
   ```

2. **Make docker.sh executable:**
   ```bash
   chmod +x docker.sh
   ```

## Usage

### Using docker.sh (Recommended)

`docker.sh` can be run from any directory and checks that Docker and a bot token are available.

| Command | What it does |
|---------|--------------|
| `./docker.sh start` | Build (cached) and start the container |
| `./docker.sh start --pull` | `git pull`, then build and start |
| `./docker.sh stop` | Stop the container |
| `./docker.sh restart` | Quick restart, no rebuild (code changes are **not** picked up) |
| `./docker.sh restart --pull` | `git pull`, rebuild and restart – use this to deploy updates |
| `./docker.sh rebuild` | `down` + full rebuild of the local code, no git pull |
| `./docker.sh status` | Container status |
| `./docker.sh logs` / `logs -f` | Last 50 log lines / follow live |
| `./docker.sh down` | Stop and remove the container (database is kept) |

### Manual Docker Compose Commands

If you prefer to use Docker Compose directly:

```bash
# Start bot
docker compose up -d

# Start with build
docker compose up --build -d

# View logs
docker compose logs -f

# View latest logs only
docker compose logs --tail=50 -f

# Check bot status
docker compose ps

# Stop bot
docker compose stop

# Stop and remove containers
docker compose down

# Stop, remove containers and images
docker compose down --rmi all

# Restart bot
docker compose restart

# Enter container shell
docker compose exec hltv-bot bash
```

## Database

The database lives in `./data/bot_data.db` on the host (mounted to `/app/data`) and survives container rebuilds.
On the very first start it is created from the team-list template that is baked into the image
(`/app/template/initial_bot_data.db`), so the bot works even with an empty `./data/` directory.

## Logs

Container logs are automatically rotated:
- Max. size per file: 10 MB
- Max. number of files: 3

## Troubleshooting

### Docker not found in WSL2

```bash
# Check if Docker Desktop is running
/mnt/c/Program\ Files/Docker/Docker/Docker\ Desktop.exe &

# Or use PowerShell directly:
# Open PowerShell in this directory and run:
docker compose up -d
```

### Container won't start

```bash
# Check logs
./docker.sh logs
# or
docker compose logs

# Rebuild container
./docker.sh rebuild
# or manually
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Database errors

```bash
# Check database permissions
ls -la data/

# Fix permissions if needed
chmod 755 data/
chmod 644 data/bot_data.db
```

## Updates

When you have code updates:

```bash
# Using docker.sh (pulls, rebuilds and restarts)
./docker.sh restart --pull

# Or manually
git pull
docker compose down
docker compose up --build -d

# Check logs
./docker.sh logs -f
```

## Resource Limits

The container has the following default limits:
- **CPU**: Max 0.5 Cores, Min 0.1 Cores
- **RAM**: Max 512 MB, Min 128 MB

These can be adjusted in `docker-compose.yml`.
