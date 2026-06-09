"""Persist crawled market data into PostgreSQL.

Design:
- `coins`       -> UPSERT (metadata changes slowly; keep one row per coin).
- `price_ticks` -> APPEND (every crawl adds a new tick, building a time series
                   that survives restarts via the Docker volume). This is the
                   durable analytics store the assistant queries later.
"""

from __future__ import annotations

from sqlalchemy import text

from src.db.connection import owner_engine

_UPSERT_COIN = text("""
    INSERT INTO coins (
        coin_id, symbol, name, market_cap_rank,
        circulating_supply, total_supply, max_supply, ath, ath_date, updated_at
    ) VALUES (
        :coin_id, :symbol, :name, :market_cap_rank,
        :circulating_supply, :total_supply, :max_supply, :ath, :ath_date, now()
    )
    ON CONFLICT (coin_id) DO UPDATE SET
        symbol             = EXCLUDED.symbol,
        name               = EXCLUDED.name,
        market_cap_rank    = EXCLUDED.market_cap_rank,
        circulating_supply = EXCLUDED.circulating_supply,
        total_supply       = EXCLUDED.total_supply,
        max_supply         = EXCLUDED.max_supply,
        ath                = EXCLUDED.ath,
        ath_date           = EXCLUDED.ath_date,
        updated_at         = now()
""")

_INSERT_TICK = text("""
    INSERT INTO price_ticks (
        coin_id, price_usd, market_cap, total_volume, high_24h, low_24h,
        price_change_24h, price_change_pct_24h, market_cap_change_pct_24h, captured_at
    ) VALUES (
        :coin_id, :price_usd, :market_cap, :total_volume, :high_24h, :low_24h,
        :price_change_24h, :price_change_pct_24h, :market_cap_change_pct_24h, :captured_at
    )
""")

_COIN_KEYS = (
    "coin_id", "symbol", "name", "market_cap_rank",
    "circulating_supply", "total_supply", "max_supply", "ath", "ath_date",
)
_TICK_KEYS = (
    "coin_id", "price_usd", "market_cap", "total_volume", "high_24h", "low_24h",
    "price_change_24h", "price_change_pct_24h", "market_cap_change_pct_24h", "captured_at",
)


def save_markets(rows: list[dict]) -> int:
    """Upsert coin metadata and append one price tick per row. Returns tick count."""
    if not rows:
        return 0
    engine = owner_engine()
    with engine.begin() as conn:
        conn.execute(_UPSERT_COIN, [{k: r[k] for k in _COIN_KEYS} for r in rows])
        conn.execute(_INSERT_TICK, [{k: r[k] for k in _TICK_KEYS} for r in rows])
    return len(rows)
