"""Kafka consumer — fan out each tick to MinIO (raw lake) + PostgreSQL (analytics).

Run:  python -m src.streaming.consumer

For every message:
  1) write the raw JSON to MinIO (durable, long-term, untouched),
  2) upsert/append it into PostgreSQL so the AI Assistant can query it.

Messages are flushed to Postgres in small batches for efficiency; MinIO writes
happen per message (the lake keeps every individual tick).
"""

from __future__ import annotations

import argparse
import json

from kafka import KafkaConsumer

from src.config import stream_config
from src.crawler.coingecko import from_json_safe
from src.crawler.store import save_markets
from src.streaming.lake import ensure_bucket, put_tick

BATCH_SIZE = 50          # flush to Postgres every N messages
BATCH_TIMEOUT_MS = 5000  # ...or at least this often


def _make_consumer(idle_timeout_ms: int | None = None) -> KafkaConsumer:
    cfg = stream_config()
    kwargs = dict(
        bootstrap_servers=cfg.kafka_bootstrap.split(","),
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=cfg.consumer_group,
    )
    # Only set a timeout for drain mode; omitting it means "block forever"
    # (passing -1 trips a selector bug in kafka-python-ng on Windows).
    if idle_timeout_ms is not None:
        kwargs["consumer_timeout_ms"] = idle_timeout_ms
    return KafkaConsumer(cfg.topic, **kwargs)


def run(drain: bool = False) -> None:
    """Consume forever, or (drain=True) until the topic is momentarily empty.

    drain mode is handy for tests and for scheduled batch runs (cron/Airflow).
    """
    ensure_bucket()
    # In drain mode, stop after 8s with no new messages; else block forever.
    consumer = _make_consumer(idle_timeout_ms=8000 if drain else None)
    cfg = stream_config()
    print(f"Consuming '{cfg.topic}' -> MinIO bucket '{cfg.minio_bucket}' + Postgres...")

    pending: list[dict] = []
    lake_count = 0
    try:
        for message in consumer:
            row = message.value

            # 1) Raw lake — store every tick, JSON as received.
            try:
                put_tick(row)
                lake_count += 1
            except Exception as exc:  # noqa: BLE001 — don't kill the stream
                print(f"  MinIO write failed: {exc}")

            # 2) Warehouse — buffer, then flush in batches.
            pending.append(from_json_safe(row))
            if len(pending) >= BATCH_SIZE:
                n = save_markets(pending)
                print(f"  flushed {n} ticks -> Postgres (lake total {lake_count})")
                pending = []
    except KeyboardInterrupt:
        print("\nStopping consumer...")
    finally:
        if pending:
            save_markets(pending)
            print(f"  final flush {len(pending)} ticks -> Postgres")
        consumer.close()
        print(f"Done. Wrote {lake_count} raw objects to MinIO.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kafka -> MinIO + Postgres consumer.")
    parser.add_argument("--drain", action="store_true",
                        help="Stop once the topic is idle (for tests / batch runs).")
    args = parser.parse_args()
    run(drain=args.drain)
