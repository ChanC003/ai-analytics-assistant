"""Tests for the streaming serialization helpers.

These cover the JSON round-trip between producer (to_json_safe) and consumer
(from_json_safe) — the easy-to-break part — without needing Kafka or a DB.
Run:  python -m pytest tests/test_streaming.py -v
"""

import json
from datetime import datetime

from src.crawler.coingecko import from_json_safe, to_json_safe


def _sample_row() -> dict:
    return {
        "coin_id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "market_cap_rank": 1,
        "ath": 126080.0,
        "ath_date": datetime(2025, 10, 6, 18, 57, 42),
        "price_usd": 62652.0,
        "price_change_pct_24h": -1.16,
        "captured_at": datetime(2026, 6, 9, 10, 13, 54),
    }


def test_to_json_safe_is_serializable():
    safe = to_json_safe(_sample_row())
    # Must survive json.dumps (datetimes turned into strings).
    s = json.dumps(safe)
    assert "2025-10-06" in s
    assert isinstance(safe["captured_at"], str)
    assert isinstance(safe["ath_date"], str)


def test_roundtrip_restores_datetimes():
    original = _sample_row()
    # Simulate Kafka: dump → load → restore.
    restored = from_json_safe(json.loads(json.dumps(to_json_safe(original))))
    assert isinstance(restored["captured_at"], datetime)
    assert isinstance(restored["ath_date"], datetime)
    assert restored["captured_at"] == original["captured_at"]
    assert restored["coin_id"] == "bitcoin"
    assert restored["price_usd"] == 62652.0


def test_none_datetime_stays_none():
    row = _sample_row()
    row["ath_date"] = None
    safe = to_json_safe(row)
    assert safe["ath_date"] is None
    restored = from_json_safe(safe)
    assert restored["ath_date"] is None
