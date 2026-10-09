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
# JSON snapshot of the last successfully fetched match list (next to the DB).
MATCH_CACHE_FILE = os.getenv(
    'MATCH_CACHE_FILE', os.path.join(os.path.dirname(DATABASE_PATH) or '.', 'match_cache.json'))
# Time of the daily match snapshot (HH:MM in TIMEZONE), before the summary.
SNAPSHOT_TIME = os.getenv('SNAPSHOT_TIME', '06:00')

# --- HLTV ---------------------------------------------------------------------
HLTV_BASE_URL = 'https://www.hltv.org'
HLTV_MATCHES_URL = f'{HLTV_BASE_URL}/matches'
HLTV_RESULTS_URL = f'{HLTV_BASE_URL}/results'
HLTV_RANKING_URL = f'{HLTV_BASE_URL}/ranking/teams'

# Minimum seconds between two requests to HLTV.
REQUEST_DELAY = 3
# How long the match list is cached (seconds). Also the refresh interval.
MATCH_CACHE_SECONDS = 30 * 60
# Max. match pages fetched per cache refresh to look up kick-off times
# (only needed if the match list ever stops carrying them).
MAX_TIME_LOOKUPS_PER_REFRESH = 40
