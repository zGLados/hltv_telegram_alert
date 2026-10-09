FROM python:3.12-slim

WORKDIR /app

# Dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
# Team-list template, outside the data volume so it is always available.
# database.py copies it to DATABASE_PATH on first start.
COPY data/initial_bot_data.db /app/template/initial_bot_data.db

ENV DATABASE_PATH=/app/data/bot_data.db \
    INITIAL_DATABASE_PATH=/app/template/initial_bot_data.db \
    PYTHONUNBUFFERED=1

VOLUME ["/app/data"]

CMD ["python", "bot.py"]
