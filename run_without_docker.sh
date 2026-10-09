#!/bin/bash
# Run the bot directly with the local virtualenv (see README → "Without Docker").
cd "$(dirname "$0")" || exit 1

if [ ! -f .env ]; then
    echo "❌ .env not found - copy .env.example to .env and add your bot token"
    exit 1
fi

if [ ! -d .venv ]; then
    echo "❌ Virtual environment not found. Run:"
    echo "   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "🚀 Starting bot..."
exec .venv/bin/python bot.py
