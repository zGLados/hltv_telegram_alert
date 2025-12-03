# Docker Setup für HLTV Telegram Bot

## Voraussetzungen

### Docker Desktop WSL2 Integration aktivieren

1. **Öffne Docker Desktop**
2. Gehe zu **Settings** (⚙️) → **Resources** → **WSL Integration**
3. Aktiviere **"Enable integration with my default WSL distro"**
4. Aktiviere auch deine spezifische WSL2 Distribution (z.B. Ubuntu)
5. Klicke **"Apply & Restart"**
6. Warte bis Docker Desktop neu gestartet ist

### Alternative: Docker ohne WSL Integration

Falls du Docker Desktop nicht in WSL integrieren möchtest, kannst du Docker-Befehle direkt aus Windows PowerShell ausführen.

## Setup

1. **Environment-Variablen konfigurieren:**
   ```bash
   cp .env.example .env
   nano .env  # Füge deinen Bot Token ein
   ```

2. **Prüfe ob alles bereit ist:**
   ```bash
   ./docker-check.sh
   ```

## Verwendung

### Bot starten

```bash
# Mit Docker Compose (empfohlen)
docker compose up -d

# Oder mit Build
docker compose up --build -d
```

### Logs ansehen

```bash
# Alle Logs
docker compose logs -f

# Nur neueste Logs
docker compose logs --tail=50 -f
```

### Bot Status prüfen

```bash
docker compose ps
```

### Bot stoppen

```bash
# Stoppen
docker compose stop

# Stoppen und Container entfernen
docker compose down

# Stoppen, Container und Images entfernen
docker compose down --rmi all
```

### Bot neu starten

```bash
docker compose restart
```

### In den Container einsteigen

```bash
docker compose exec hltv-bot bash
```

## Datenbank

Die Datenbank wird im `./data/` Verzeichnis gespeichert und bleibt auch nach dem Löschen des Containers erhalten.

## Logs

Container-Logs werden automatisch rotiert:
- Max. Größe pro Datei: 10 MB
- Max. Anzahl Dateien: 3

## Troubleshooting

### Docker nicht gefunden in WSL2

```bash
# Prüfe ob Docker Desktop läuft
/mnt/c/Program\ Files/Docker/Docker/Docker\ Desktop.exe &

# Oder nutze PowerShell direkt:
# Öffne PowerShell in diesem Verzeichnis und führe aus:
docker compose up -d
```

### Container startet nicht

```bash
# Logs prüfen
docker compose logs

# Container neu bauen
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Datenbank-Fehler

```bash
# Datenbank-Rechte prüfen
ls -la data/

# Falls nötig, Rechte anpassen
chmod 755 data/
chmod 644 data/bot_data.db
```

## Updates

Wenn du den Code aktualisiert hast:

```bash
# Bot stoppen
docker compose down

# Neu bauen und starten
docker compose up --build -d

# Logs prüfen
docker compose logs -f
```

## Ressourcen-Limits

Der Container hat standardmäßig:
- **CPU**: Max 0.5 Cores, Min 0.1 Cores
- **RAM**: Max 512 MB, Min 128 MB

Diese können in `docker-compose.yml` angepasst werden.
