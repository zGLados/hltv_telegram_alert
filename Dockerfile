FROM python:3.12-slim

WORKDIR /app

# Dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hltv_bot/ ./hltv_bot/
# Team-list template, outside the data volume so it is always available.
# The bot copies it to DATABASE_PATH on first start.
COPY assets/initial_bot_data.db ./assets/initial_bot_data.db

ENV DATABASE_PATH=/app/data/bot_data.db \
    INITIAL_DATABASE_PATH=/app/assets/initial_bot_data.db \
    PYTHONUNBUFFERED=1

VOLUME ["/app/data"]

CMD ["python", "-m", "hltv_bot"]
