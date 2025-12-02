#!/bin/bash

# Farben für Output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  HLTV Telegram Bot - Docker Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Prüfe ob .env existiert
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env Datei nicht gefunden!${NC}"
    echo -e "${YELLOW}Erstelle .env aus .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ .env Datei erstellt${NC}"
    echo ""
    echo -e "${RED}WICHTIG: Bitte trage deinen Telegram Bot Token in die .env Datei ein!${NC}"
    echo -e "Öffne die Datei und ersetze 'your_bot_token_here' mit deinem echten Token."
    echo ""
    echo "Starte danach den Bot mit: ./start.sh"
    exit 1
fi

# Prüfe ob Token gesetzt ist
source .env
if [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ] || [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}❌ Telegram Bot Token ist nicht konfiguriert!${NC}"
    echo ""
    echo "Bitte trage deinen Token in die .env Datei ein:"
    echo "1. Öffne .env"
    echo "2. Ersetze 'your_bot_token_here' mit deinem echten Token"
    echo "3. Führe dieses Script erneut aus"
    exit 1
fi

# Erstelle data Verzeichnis falls nicht vorhanden
if [ ! -d "data" ]; then
    echo -e "${YELLOW}📁 Erstelle data Verzeichnis...${NC}"
    mkdir -p data
    echo -e "${GREEN}✅ data Verzeichnis erstellt${NC}"
fi

echo -e "${BLUE}🐳 Starte Docker Container...${NC}"
echo ""

# Verwende docker compose (v2) statt docker-compose (v1)
DOCKER_COMPOSE="docker compose"

# Stoppe alte Container falls vorhanden
$DOCKER_COMPOSE down 2>/dev/null

# Baue und starte Container
$DOCKER_COMPOSE up --build -d

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✅ Bot erfolgreich gestartet!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "📊 Container Status:"
    $DOCKER_COMPOSE ps
    echo ""
    echo "📝 Logs anzeigen:"
    echo "   docker compose logs -f"
    echo ""
    echo "🛑 Bot stoppen:"
    echo "   docker compose down"
    echo ""
    echo "🔄 Bot neu starten:"
    echo "   docker compose restart"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Fehler beim Starten des Bots${NC}"
    echo ""
    echo "Überprüfe die Logs mit:"
    echo "   docker compose logs"
    exit 1
fi
