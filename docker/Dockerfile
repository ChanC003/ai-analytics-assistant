# Image for the producer + consumer containers (the always-on ingest workers).
FROM python:3.12-slim

# Unbuffered stdout so `docker logs` shows producer/consumer output live.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# Default command is overridden per-service in docker-compose.
CMD ["python", "-m", "src.streaming.producer", "--loop", "--interval", "60"]
