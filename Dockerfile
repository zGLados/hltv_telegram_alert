FROM python:3.12-slim

# Setze Arbeitsverzeichnis
WORKDIR /app

# Kopiere Requirements und installiere Python-Pakete
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere Anwendungscode
COPY . .

# Erstelle Volume für Datenbank
VOLUME ["/app/data"]

# Environment-Variable für Datenbank-Pfad
ENV DATABASE_PATH=/app/data/bot_data.db

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('${DATABASE_PATH}') else 1)"

# Starte Bot
CMD ["python", "-u", "bot.py"]
