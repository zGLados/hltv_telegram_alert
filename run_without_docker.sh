#!/bin/bash

# Farben
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  HLTV Telegram Bot - Start${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Prüfe .env
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env Datei nicht gefunden!${NC}"
    exit 1
fi

# Aktiviere venv
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment nicht gefunden!${NC}"
    echo "Führe erst 'python -m venv .venv' und 'pip install -r requirements.txt' aus"
    exit 1
fi

source .venv/bin/activate

# Erstelle data Verzeichnis
mkdir -p data

echo -e "${GREEN}🚀 Starte Bot...${NC}"
echo ""

# Starte Bot
python bot.py
