import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Telegram Bot Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Berlin')
DAILY_SUMMARY_TIME = os.getenv('DAILY_SUMMARY_TIME', '09:00')

# HLTV URLs
HLTV_BASE_URL = 'https://www.hltv.org'
HLTV_MATCHES_URL = f'{HLTV_BASE_URL}/matches'
HLTV_RESULTS_URL = f'{HLTV_BASE_URL}/results'

# User Agent for HLTV Requests - Aktuelle Chrome-Version
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Cache-Control': 'max-age=0',
    'Referer': 'https://www.hltv.org/',
    'DNT': '1'
}

# Datenbank
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/bot_data.db')

# Match Wichtigkeit (Sterne auf HLTV)
MIN_STARS_FOR_IMPORTANT = 1  # At least 1 star for "important" matches
