#!/bin/bash

# Stop any running bot instance
echo "Stopping running bot..."
pkill -f "python.*bot.py" 2>/dev/null || true

echo ""
echo "======================================"
echo "Starting HLTV Telegram Bot with Docker"
echo "======================================"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ist nicht verfügbar!"
    echo ""
    echo "Bitte aktiviere Docker Desktop WSL2 Integration oder"
    echo "führe diesen Befehl in PowerShell aus:"
    echo ""
    echo "  cd $(pwd)"
    echo "  docker compose up -d"
    echo ""
    exit 1
fi

# Build and start
echo "Building and starting container..."
docker compose up --build -d

echo ""
echo "✅ Bot gestartet!"
echo ""
echo "Logs ansehen:"
echo "  docker compose logs -f"
echo ""
echo "Bot stoppen:"
echo "  docker compose down"
echo ""
