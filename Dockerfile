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

# Copy initial database template if bot_data.db doesn't exist
RUN mkdir -p /app/data

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('${DATABASE_PATH}') else 1)"

# Startup script to copy template DB if needed
RUN echo '#!/bin/bash\n\
if [ ! -f /app/data/bot_data.db ] && [ -f /app/data/initial_bot_data.db ]; then\n\
  echo "Copying initial database template..."\n\
  cp /app/data/initial_bot_data.db /app/data/bot_data.db\n\
  echo "✅ Database initialized with 259 teams"\n\
fi\n\
exec python -u bot.py' > /app/start.sh && chmod +x /app/start.sh

# Starte Bot
CMD ["/app/start.sh"]
