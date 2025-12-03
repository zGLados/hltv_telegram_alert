#!/bin/bash

echo "======================================"
echo "HLTV Telegram Bot - Docker Setup Check"
echo "======================================"
echo ""

# Check Docker availability
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ist nicht verfügbar in WSL2"
    echo ""
    echo "Bitte aktiviere Docker Desktop WSL2 Integration:"
    echo "1. Öffne Docker Desktop"
    echo "2. Gehe zu Settings → Resources → WSL Integration"
    echo "3. Aktiviere Integration für deine WSL2 Distribution"
    echo "4. Klicke 'Apply & Restart'"
    echo ""
    exit 1
fi

echo "✅ Docker ist verfügbar"
docker --version
echo ""

# Check docker-compose
if command -v docker-compose &> /dev/null; then
    echo "✅ docker-compose ist verfügbar"
    docker-compose --version
else
    echo "⚠️  docker-compose nicht gefunden, aber 'docker compose' sollte funktionieren"
fi
echo ""

# Check .env file
if [ ! -f .env ]; then
    echo "❌ .env Datei fehlt!"
    echo "   Kopiere .env.example zu .env und füge deinen Bot Token ein"
    exit 1
fi

echo "✅ .env Datei vorhanden"
echo ""

# Check data directory
if [ ! -d data ]; then
    echo "📁 Erstelle data/ Verzeichnis..."
    mkdir -p data
fi
echo "✅ data/ Verzeichnis vorhanden"
echo ""

echo "======================================"
echo "Setup ist bereit! Du kannst jetzt starten mit:"
echo ""
echo "  docker compose up --build -d"
echo ""
echo "Logs ansehen:"
echo "  docker compose logs -f"
echo ""
echo "Bot stoppen:"
echo "  docker compose down"
echo ""
echo "======================================"
