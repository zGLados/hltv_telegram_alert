import os
import sys
import tempfile

# Config is read at import time; give it harmless defaults for tests and keep
# the module-level Database in bot.py away from the real data/ directory.
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test-token')
os.environ.setdefault('TIMEZONE', 'Europe/Berlin')
os.environ['DATABASE_PATH'] = os.path.join(tempfile.mkdtemp(), 'bot_data.db')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
