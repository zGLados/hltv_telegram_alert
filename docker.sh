#!/bin/bash

# Output colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Docker Compose Command
DOCKER_COMPOSE="docker compose"

cd "$(dirname "$0")" || exit 1

# Functions
show_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  HLTV Telegram Bot - Docker Manager${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found${NC}"
        echo "WSL2: enable Docker Desktop → Settings → Resources → WSL Integration"
        exit 1
    fi
}

check_env() {
    check_docker
    if [ ! -f .env ]; then
        echo -e "${YELLOW}⚠️  .env file not found!${NC}"
        echo -e "${YELLOW}Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${GREEN}✅ .env file created${NC}"
        echo ""
        echo -e "${RED}IMPORTANT: Please add your Telegram Bot Token to the .env file!${NC}"
        echo -e "Open the file and replace 'your_bot_token_here' with your actual token."
        echo ""
        echo "Then start the bot with: ./docker.sh start"
        exit 1
    fi

    source .env
    if [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ] || [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        echo -e "${RED}❌ Telegram Bot Token is not configured!${NC}"
        echo ""
        echo "Please add your token to the .env file:"
        echo "1. Open .env"
        echo "2. Replace 'your_bot_token_here' with your actual token"
        echo "3. Run this script again"
        exit 1
    fi
}

create_data_dir() {
    if [ ! -d "data" ]; then
        echo -e "${YELLOW}📁 Creating data directory...${NC}"
        mkdir -p data
        echo -e "${GREEN}✅ data directory created${NC}"
    fi
}

start_bot() {
    show_header
    echo -e "${BLUE}🚀 Starting bot...${NC}"
    echo ""
    
    check_env
    create_data_dir
    
    # Check for --pull flag
    if [ "$1" = "--pull" ]; then
        if [ -d .git ]; then
            echo -e "${BLUE}📥 Pulling latest changes from git...${NC}"
            git pull
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Git pull successful${NC}"
            else
                echo -e "${YELLOW}⚠️  Git pull failed - continuing with local version${NC}"
            fi
            echo ""
        fi
    fi
    
    echo -e "${BLUE}🐳 Building and starting Docker container...${NC}"
    # --build is cheap thanks to layer caching and makes sure pulled code is used
    $DOCKER_COMPOSE up -d --build
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  ✅ Bot successfully started!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        show_status
    else
        echo ""
        echo -e "${RED}❌ Error starting bot${NC}"
        echo ""
        echo "Check logs with:"
        echo "   ./docker.sh logs"
        exit 1
    fi
}

stop_bot() {
    show_header
    echo -e "${YELLOW}🛑 Stopping bot...${NC}"
    echo ""
    
    $DOCKER_COMPOSE stop
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Bot stopped${NC}"
    else
        echo ""
        echo -e "${RED}❌ Error stopping bot${NC}"
        exit 1
    fi
}

restart_bot() {
    show_header
    echo -e "${BLUE}🔄 Restarting bot...${NC}"
    echo ""
    
    # Check if --pull flag is provided
    if [ "$1" = "--pull" ]; then
        echo -e "${CYAN}📥 Pulling latest changes from Git...${NC}"
        git pull
        if [ $? -ne 0 ]; then
            echo ""
            echo -e "${RED}❌ Git pull failed${NC}"
            exit 1
        fi
        echo ""
        echo -e "${CYAN}🔨 Rebuilding container with latest changes...${NC}"
        echo ""
        $DOCKER_COMPOSE up -d --build
    else
        $DOCKER_COMPOSE restart
    fi
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Bot restarted${NC}"
        echo ""
        show_status
    else
        echo ""
        echo -e "${RED}❌ Error restarting bot${NC}"
        exit 1
    fi
}

rebuild_bot() {
    show_header
    echo -e "${BLUE}🔨 Rebuilding bot...${NC}"
    echo ""
    
    check_env
    
    echo -e "${YELLOW}Stopping existing containers...${NC}"
    $DOCKER_COMPOSE down
    
    echo ""
    echo -e "${BLUE}Building and starting with fresh image...${NC}"
    $DOCKER_COMPOSE up --build -d
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Bot rebuilt and started${NC}"
        echo ""
        show_status
    else
        echo ""
        echo -e "${RED}❌ Error rebuilding bot${NC}"
        exit 1
    fi
}

show_status() {
    echo "📊 Container Status:"
    $DOCKER_COMPOSE ps
    echo ""
}

show_logs() {
    if [ "$1" = "-f" ] || [ "$1" = "--follow" ]; then
        echo -e "${BLUE}📝 Showing live logs (Ctrl+C to exit)...${NC}"
        echo ""
        $DOCKER_COMPOSE logs -f
    else
        echo -e "${BLUE}📝 Showing last 50 log lines...${NC}"
        echo ""
        $DOCKER_COMPOSE logs --tail=50
        echo ""
        echo -e "${YELLOW}Tip: Use './docker.sh logs -f' for live logs${NC}"
    fi
}

down_bot() {
    show_header
    echo -e "${RED}🗑️  Removing containers...${NC}"
    echo ""
    
    $DOCKER_COMPOSE down
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Containers removed (database preserved in ./data/)${NC}"
    else
        echo ""
        echo -e "${RED}❌ Error removing containers${NC}"
        exit 1
    fi
}

show_help() {
    show_header
    echo "Usage: ./docker.sh [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start            Start the bot"
    echo "  start --pull     Pull latest changes from git, then start"
    echo "  stop             Stop the bot"
    echo "  restart          Restart the bot"
    echo "  restart --pull   Pull latest changes, rebuild and restart"
    echo "  rebuild          Rebuild and restart the bot"
    echo "  status           Show container status"
    echo "  logs             Show last 50 log lines"
    echo "  logs -f          Show live logs (follow)"
    echo "  down             Stop and remove containers"
    echo "  help             Show this help"
    echo ""
    echo "Examples:"
    echo "  ./docker.sh start"
    echo "  ./docker.sh start --pull"
    echo "  ./docker.sh restart --pull"
    echo "  ./docker.sh logs -f"
    echo "  ./docker.sh rebuild"
    echo ""
}

# Main
case "$1" in
    start)
        start_bot "$2"
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot "$2"
        ;;
    rebuild)
        rebuild_bot
        ;;
    status)
        show_header
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    down)
        down_bot
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        ;;
esac
