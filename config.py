"""Runtime configuration, read from environment variables (and an optional .env file)."""
import os
from datetime import time as dtime

import pytz
from dotenv import load_dotenv

load_dotenv()

# --- Telegram -----------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Timezone used for "today", the daily summary and all displayed match times.
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Berlin')
TZ = pytz.timezone(TIMEZONE)

# Time of the daily summary, format HH:MM (interpreted in TIMEZONE).
DAILY_SUMMARY_TIME = os.getenv('DAILY_SUMMARY_TIME', '09:00')
_hour, _minute = map(int, DAILY_SUMMARY_TIME.split(':'))
DAILY_SUMMARY_AT = dtime(hour=_hour, minute=_minute)

# --- Storage ------------------------------------------------------------------
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/bot_data.db')
# Shipped template with the pre-loaded team list; copied on first start.
INITIAL_DATABASE_PATH = os.getenv('INITIAL_DATABASE_PATH', 'data/initial_bot_data.db')

# --- HLTV ---------------------------------------------------------------------
HLTV_BASE_URL = 'https://www.hltv.org'
HLTV_MATCHES_URL = f'{HLTV_BASE_URL}/matches'
HLTV_RESULTS_URL = f'{HLTV_BASE_URL}/results'

# Minimum seconds between two requests to HLTV.
REQUEST_DELAY = 3
# How long the match list is cached (seconds). Also the refresh interval.
MATCH_CACHE_SECONDS = 30 * 60
# Max. match pages fetched per cache refresh to look up kick-off times.
MAX_TIME_LOOKUPS_PER_REFRESH = 40

# Browser-like headers for HLTV requests. "zstd" is deliberately not offered:
# requests cannot decode it and would hand us garbage.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
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
    'DNT': '1',
}
