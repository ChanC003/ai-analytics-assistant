"""Kafka producer — crawl CoinGecko and publish each coin tick to a topic.

Run one batch:   python -m src.streaming.producer --once
Run continuously: python -m src.streaming.producer --loop --interval 60

This is the ingest source. The consumer (src/streaming/consumer.py) fans each
message out to MinIO (raw lake) and PostgreSQL (analytics).
"""

from __future__ import annotations

import argparse
import json
import time

from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.config import stream_config
from src.crawler.coingecko import CoinGeckoError, fetch_markets, to_json_safe


def _make_producer() -> KafkaProducer:
    cfg = stream_config()
    return KafkaProducer(
        bootstrap_servers=cfg.kafka_bootstrap.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",          # wait for the broker to persist
        retries=3,
    )


def publish_once(producer: KafkaProducer, per_page: int = 50) -> int:
    """Crawl one snapshot and publish each coin as a message. Returns count sent."""
    cfg = stream_config()
    rows = fetch_markets(per_page=per_page)
    for row in rows:
        # Keyed by coin_id so all ticks of a coin land in the same partition
        # (preserves per-coin ordering).
        producer.send(cfg.topic, key=row["coin_id"], value=to_json_safe(row))
    producer.flush()
    return len(rows)


def run_loop(interval: int = 60, per_page: int = 50) -> None:
    producer = _make_producer()
    cfg = stream_config()
    print(f"Producing to '{cfg.topic}' every {interval}s (Ctrl+C to stop)...")
    try:
        while True:
            try:
                n = publish_once(producer, per_page=per_page)
                print(f"[{time.strftime('%H:%M:%S')}] published {n} ticks")
            except CoinGeckoError as exc:
                print(f"[{time.strftime('%H:%M:%S')}] fetch error: {exc}")
            except KafkaError as exc:
                print(f"[{time.strftime('%H:%M:%S')}] kafka error: {exc}")
            time.sleep(interval)
    finally:
        producer.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CoinGecko → Kafka producer.")
    parser.add_argument("--once", action="store_true", help="Publish one batch then exit.")
    parser.add_argument("--loop", action="store_true", help="Publish continuously.")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--per-page", type=int, default=50)
    args = parser.parse_args()

    if args.loop:
        run_loop(interval=args.interval, per_page=args.per_page)
    else:
        p = _make_producer()
        try:
            count = publish_once(p, per_page=args.per_page)
            print(f"Published {count} ticks to Kafka.")
        finally:
            p.close()
