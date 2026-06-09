"""MinIO (S3) writer — the raw data lake. Stores every tick as JSON, untouched.

Layout (partitioned by date + coin for easy reprocessing later):
    crypto-raw/ticks/dt=YYYY-MM-DD/<coin_id>/<captured_at>.json

Keeping the raw bytes means we can always re-derive the warehouse tables — the
lake is the long-term source of truth.
"""

from __future__ import annotations

import json
from functools import lru_cache

import boto3
from botocore.config import Config

from src.config import stream_config


@lru_cache(maxsize=1)
def _s3_client():
    cfg = stream_config()
    scheme = "https" if cfg.minio_secure else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{cfg.minio_endpoint}",
        aws_access_key_id=cfg.minio_access_key,
        aws_secret_access_key=cfg.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    """Create the bucket if it doesn't exist (idempotent)."""
    cfg = stream_config()
    s3 = _s3_client()
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if cfg.minio_bucket not in existing:
        s3.create_bucket(Bucket=cfg.minio_bucket)


def put_tick(row: dict) -> str:
    """Write one tick (JSON-safe dict) to the lake. Returns the object key."""
    cfg = stream_config()
    captured = str(row.get("captured_at", ""))
    dt = captured[:10] or "unknown"            # YYYY-MM-DD
    coin = row.get("coin_id", "unknown")
    # Colons aren't ideal in S3 keys; flatten the timestamp.
    stamp = captured.replace(":", "").replace("-", "").replace(".", "")
    key = f"ticks/dt={dt}/{coin}/{stamp}.json"

    _s3_client().put_object(
        Bucket=cfg.minio_bucket,
        Key=key,
        Body=json.dumps(row).encode("utf-8"),
        ContentType="application/json",
    )
    return key
