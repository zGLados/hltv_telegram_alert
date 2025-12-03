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

The `docker.sh` script provides convenient management commands:

```bash
# Start bot (automatically pulls latest git changes and builds)
./docker.sh start

# Stop bot
./docker.sh stop

# Restart bot (quick restart without rebuild)
./docker.sh restart

# Rebuild bot (pulls git changes and does full rebuild)
./docker.sh rebuild

# View logs
./docker.sh logs

# View logs with live updates
./docker.sh logs -f

# Check container status
./docker.sh status
```

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

The database is stored in the `./data/` directory and persists even after deleting the container.

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
# Using docker.sh (automatically pulls latest git changes)
./docker.sh rebuild

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

## Auto-Update Feature

The `docker.sh start` and `docker.sh rebuild` commands automatically pull the latest changes from git before building, ensuring you're always running the most recent version.
