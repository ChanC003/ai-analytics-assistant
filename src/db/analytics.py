"""Pre-built analytics queries for the Market Dashboard.

These power the always-on charts (no LLM needed) — fast, cached reads off the
warehouse. Kept separate from the LLM path so the dashboard works even with no
API key configured.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from src.db.connection import owner_engine

# Latest snapshot = the most recent crawl batch.
_LATEST = "(SELECT MAX(captured_at) FROM price_ticks)"


def _df(sql: str) -> pd.DataFrame:
    with owner_engine().connect() as conn:
        return pd.read_sql(text(sql), conn)


def kpis() -> dict:
    """Headline numbers for the KPI strip."""
    sql = f"""
        SELECT
          (SELECT COUNT(*) FROM coins)                              AS coins,
          (SELECT COUNT(DISTINCT captured_at) FROM price_ticks)     AS snapshots,
          (SELECT COUNT(*) FROM price_ticks)                        AS ticks,
          (SELECT MAX(captured_at) FROM price_ticks)                AS last_crawl,
          (SELECT SUM(market_cap) FROM price_ticks WHERE captured_at = {_LATEST}) AS total_mcap,
          (SELECT SUM(total_volume) FROM price_ticks WHERE captured_at = {_LATEST}) AS total_volume
    """
    row = _df(sql)
    return {} if row.empty else row.iloc[0].to_dict()


def top_by_market_cap(limit: int = 10) -> pd.DataFrame:
    return _df(f"""
        SELECT c.name, c.symbol, t.market_cap, t.price_usd, t.price_change_pct_24h
        FROM price_ticks t
        JOIN coins c ON c.coin_id = t.coin_id
        WHERE t.captured_at = {_LATEST} AND t.market_cap IS NOT NULL
        ORDER BY t.market_cap DESC
        LIMIT {limit}
    """)


def movers_24h(limit: int = 8) -> pd.DataFrame:
    """Top gainers and losers in one frame (for a diverging bar)."""
    gainers = _df(f"""
        SELECT c.symbol, c.name, t.price_change_pct_24h AS pct
        FROM price_ticks t JOIN coins c ON c.coin_id = t.coin_id
        WHERE t.captured_at = {_LATEST} AND t.price_change_pct_24h IS NOT NULL
        ORDER BY t.price_change_pct_24h DESC
        LIMIT {limit}
    """)
    losers = _df(f"""
        SELECT c.symbol, c.name, t.price_change_pct_24h AS pct
        FROM price_ticks t JOIN coins c ON c.coin_id = t.coin_id
        WHERE t.captured_at = {_LATEST} AND t.price_change_pct_24h IS NOT NULL
        ORDER BY t.price_change_pct_24h ASC
        LIMIT {limit}
    """)
    out = pd.concat([gainers, losers], ignore_index=True).drop_duplicates("symbol")
    out["direction"] = out["pct"].apply(lambda v: "gain" if v >= 0 else "loss")
    return out


def price_history(symbols: list[str]) -> pd.DataFrame:
    """Time series of price for the given coin symbols across all snapshots."""
    if not symbols:
        return pd.DataFrame(columns=["captured_at", "symbol", "price_usd"])
    placeholders = ", ".join(f"'{s.lower()}'" for s in symbols)
    return _df(f"""
        SELECT t.captured_at, c.symbol, t.price_usd
        FROM price_ticks t
        JOIN coins c ON c.coin_id = t.coin_id
        WHERE LOWER(c.symbol) IN ({placeholders})
        ORDER BY t.captured_at
    """)


def volume_leaders(limit: int = 10) -> pd.DataFrame:
    return _df(f"""
        SELECT c.symbol, c.name, t.total_volume
        FROM price_ticks t JOIN coins c ON c.coin_id = t.coin_id
        WHERE t.captured_at = {_LATEST} AND t.total_volume IS NOT NULL
        ORDER BY t.total_volume DESC
        LIMIT {limit}
    """)


def sentiment_split() -> pd.DataFrame:
    """Count of coins up vs down vs flat in the latest snapshot (market sentiment)."""
    return _df(f"""
        SELECT
          CASE
            WHEN price_change_pct_24h > 0 THEN 'Gainers'
            WHEN price_change_pct_24h < 0 THEN 'Losers'
            ELSE 'Flat'
          END AS bucket,
          COUNT(*) AS n
        FROM price_ticks
        WHERE captured_at = {_LATEST} AND price_change_pct_24h IS NOT NULL
        GROUP BY 1
    """)


def available_symbols(limit: int = 30) -> list[str]:
    """Symbols of the largest coins — for the price-history picker."""
    df = _df(f"""
        SELECT c.symbol
        FROM price_ticks t JOIN coins c ON c.coin_id = t.coin_id
        WHERE t.captured_at = {_LATEST}
        ORDER BY t.market_cap DESC NULLS LAST
        LIMIT {limit}
    """)
    return df["symbol"].str.upper().tolist()
