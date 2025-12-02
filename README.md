# 🎮 HLTV Telegram Alert Bot

Ein Telegram Bot, der dich über die wichtigsten CS:GO/CS2-Matches auf HLTV.org informiert und Benachrichtigungen über deine Lieblingsteams sendet.

## Features

✅ **Tägliche Match-Übersicht** - Erhalte jeden Morgen eine Zusammenfassung der wichtigsten Matches des Tages  
✅ **Lieblingsteams verwalten** - Füge deine Favoriten-Teams hinzu und erhalte Benachrichtigungen  
✅ **Live-Ergebnisse** - Automatische Updates wenn Spiele deiner Lieblingsteams enden  
✅ **Sterne-Filter** - Nur wichtige Matches (basierend auf HLTV Stern-Rating)  
✅ **Einfache Bedienung** - Intuitive Commands zur Verwaltung

## Installation

### Option 1: Mit Docker (Empfohlen) 🐳

**Voraussetzungen:**
- Docker und Docker Compose installiert

**Schritte:**

1. **Repository klonen**
   ```bash
   git clone https://github.com/zGLados/hltv_telegram_alert.git
   cd hltv_telegram_alert
   ```

2. **Telegram Bot erstellen**
   - Öffne Telegram und suche nach [@BotFather](https://t.me/BotFather)
   - Sende `/newbot` und folge den Anweisungen
   - Kopiere den API-Token

3. **Konfiguration**
   ```bash
   cp .env.example .env
   ```
   Bearbeite `.env` und trage deinen Bot-Token ein:
   ```env
   TELEGRAM_BOT_TOKEN=dein_bot_token_hier
   TIMEZONE=Europe/Berlin
   DAILY_SUMMARY_TIME=09:00
   ```

4. **Bot starten**
   ```bash
   ./start.sh
   ```
   
   Oder manuell:
   ```bash
   docker compose up -d
   ```

5. **Logs anzeigen**
   ```bash
   docker compose logs -f
   ```

6. **Bot stoppen**
   ```bash
   docker compose down
   ```

### Option 2: Ohne Docker

**Voraussetzungen:**
- Python 3.12 oder höher

**Schritte:**

### 1. Repository klonen

```bash
git clone https://github.com/zGLados/hltv_telegram_alert.git
cd hltv_telegram_alert
```

### 2. Python-Umgebung einrichten

```bash
python -m venv .venv
source .venv/bin/activate  # Auf Windows: .venv\Scripts\activate
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 4. Telegram Bot erstellen

1. Öffne Telegram und suche nach [@BotFather](https://t.me/BotFather)
2. Sende `/newbot` und folge den Anweisungen
3. Kopiere den API-Token, den du erhältst

### 5. Konfiguration

Erstelle eine `.env` Datei im Projektverzeichnis:

```bash
cp .env.example .env
```

Bearbeite die `.env` Datei und füge deinen Bot-Token ein:

```env
TELEGRAM_BOT_TOKEN=dein_bot_token_hier
TIMEZONE=Europe/Berlin
DAILY_SUMMARY_TIME=09:00
```

## Verwendung

### Bot starten

```bash
python bot.py
```

Der Bot läuft nun und ist über Telegram erreichbar!

### Verfügbare Commands

| Command | Beschreibung |
|---------|--------------|
| `/start` | Begrüßungsnachricht und Übersicht |
| `/help` | Hilfe und Anleitung |
| `/today` | Zeigt die wichtigsten Matches von heute |
| `/favorites` | Zeigt deine Lieblingsteams |
| `/add` | Füge ein Lieblingsteam hinzu |
| `/remove` | Entferne ein Lieblingsteam |

### Beispiel-Workflow

1. Starte den Bot mit `/start`
2. Füge deine Lieblingsteams hinzu:
   ```
   /add
   FaZe
   ```
3. Prüfe die heutigen Matches:
   ```
   /today
   ```
4. Der Bot sendet automatisch:
   - Tägliche Zusammenfassung um 09:00 Uhr
   - Benachrichtigungen über Spiele deiner Favoriten
   - Ergebnisse nach Spielende

## Konfiguration

In der `config.py` kannst du folgende Einstellungen anpassen:

- `MIN_STARS_FOR_IMPORTANT`: Mindestanzahl an Sternen für "wichtige" Matches (Standard: 1)
- `DAILY_SUMMARY_TIME`: Zeit für die tägliche Zusammenfassung (Standard: 09:00)
- `TIMEZONE`: Zeitzone für Benachrichtigungen (Standard: Europe/Berlin)

## Automatische Benachrichtigungen

Der Bot überprüft:
- **Täglich um 09:00 Uhr**: Sendet eine Zusammenfassung aller wichtigen Matches
- **Alle 30 Minuten**: Überprüft ob Spiele deiner Lieblingsteams beendet wurden

## Technische Details

### Architektur

```
├── bot.py              # Hauptdatei mit Bot-Logik
├── hltv_scraper.py    # HLTV.org Scraper
├── database.py        # SQLite Datenbank-Verwaltung
├── config.py          # Konfiguration
└── requirements.txt   # Python-Abhängigkeiten
```

### Verwendete Technologien

- **python-telegram-bot** - Telegram Bot API
- **BeautifulSoup4** - Web Scraping
- **APScheduler** - Zeitgesteuerte Aufgaben
- **SQLite** - Datenbank für Benutzer-Favoriten

## Fehlerbehebung

### Bot antwortet nicht

1. Prüfe ob der Bot läuft: `python bot.py`
2. Überprüfe den Token in der `.env` Datei
3. Stelle sicher, dass du mit dem Bot in Telegram eine Konversation gestartet hast (`/start`)

### Keine Matches gefunden

- HLTV.org könnte temporär nicht erreichbar sein
- Überprüfe deine Internetverbindung
- Möglicherweise gibt es heute keine wichtigen Matches

### Benachrichtigungen kommen nicht an

- Stelle sicher, dass du Favoriten hinzugefügt hast (`/favorites`)
- Überprüfe die Zeitzone in der `.env` Datei
- Prüfe ob deine Lieblingsteams heute spielen

## Deployment

### Docker (Produktiv-Umgebung)

Der Bot läuft bereits als Docker-Container wenn du `./start.sh` oder `docker-compose up -d` verwendet hast.

**Nützliche Befehle:**

```bash
# Status prüfen
docker compose ps

# Logs anzeigen
docker compose logs -f

# Bot neu starten
docker compose restart

# Bot stoppen
docker compose down

# Container neu bauen
docker compose up --build -d

# In Container einloggen (für Debugging)
docker compose exec hltv-bot /bin/bash
```

### Systemd Service (ohne Docker)

Erstelle `/etc/systemd/system/hltv-bot.service`:

```ini
[Unit]
Description=HLTV Telegram Bot
After=network.target

[Service]
Type=simple
User=dein_username
WorkingDirectory=/pfad/zum/hltv_telegram_alert
Environment="PATH=/pfad/zum/hltv_telegram_alert/.venv/bin"
ExecStart=/pfad/zum/hltv_telegram_alert/.venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Aktivieren:
```bash
sudo systemctl enable hltv-bot
sudo systemctl start hltv-bot
```

### Server-Deployment mit Docker

Für einen produktiven Server empfiehlt sich:

1. **Automatischer Start nach Reboot:**
   
   Die `docker-compose.yml` verwendet bereits `restart: unless-stopped`

2. **Backup der Datenbank:**
   ```bash
   # Backup erstellen
   docker compose exec hltv-bot cp /app/data/bot_data.db /app/data/backup_$(date +%Y%m%d).db
   
   # Oder vom Host
   cp data/bot_data.db data/backup_$(date +%Y%m%d).db
   ```

3. **Updates einspielen:**
   ```bash
   git pull
   docker compose down
   docker compose up --build -d
   ```

4. **Monitoring:**
   ```bash
   # Ressourcen-Nutzung
   docker stats hltv-telegram-bot
   
   # Logs der letzten Stunde
   docker compose logs --since 1h
   ```

### Mit Docker Swarm oder Kubernetes

Für Swarm:
```bash
docker stack deploy -c docker-compose.yml hltv-bot
```

Für Kubernetes kannst du die Docker-Images verwenden und entsprechende Deployments erstellen.

### Mit Docker (manuell ohne Compose)

```bash
# Image bauen
docker build -t hltv-bot .

# Container starten
docker run -d \
  --name hltv-telegram-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  hltv-bot

# Logs anzeigen
docker logs -f hltv-telegram-bot

# Stoppen
docker stop hltv-telegram-bot
docker rm hltv-telegram-bot
```

## Lizenz

MIT License

## Mitwirken

Pull Requests sind willkommen! Für größere Änderungen öffne bitte zuerst ein Issue.

## Disclaimer

Dieser Bot ist ein inoffizielles Projekt und nicht mit HLTV.org verbunden. Verwende ihn verantwortungsvoll und überlaste die HLTV.org Server nicht.