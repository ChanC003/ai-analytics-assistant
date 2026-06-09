"""Build the schema context (DDL-ish + sample rows) injected into the LLM prompt.

Schema-aware prompting is what keeps generated SQL grounded in real columns.
The result is cached because the schema rarely changes within a session.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text

from src.db.connection import owner_engine

# Tables we expose to the assistant (order chosen for readability in the prompt).
_TABLES = ["coins", "price_ticks"]


def _columns(conn, table: str) -> list[tuple[str, str]]:
    rows = conn.execute(
        text(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t "
            "ORDER BY ordinal_position"
        ),
        {"t": table},
    ).all()
    return [(r[0], r[1]) for r in rows]


def _sample_rows(conn, table: str, limit: int = 3) -> list[dict]:
    rows = conn.execute(text(f"SELECT * FROM {table} LIMIT {limit}")).mappings().all()
    return [dict(r) for r in rows]


@lru_cache(maxsize=1)
def schema_context() -> str:
    """Return a compact text description of every table + a few sample rows."""
    parts: list[str] = []
    engine = owner_engine()
    with engine.connect() as conn:
        for table in _TABLES:
            cols = _columns(conn, table)
            if not cols:
                continue
            col_lines = ", ".join(f"{name} {dtype}" for name, dtype in cols)
            samples = _sample_rows(conn, table)
            sample_text = "\n".join(f"      {row}" for row in samples) or "      (no rows)"
            parts.append(
                f"TABLE {table} ({col_lines})\n"
                f"    sample rows:\n{sample_text}"
            )

    relationships = (
        "RELATIONSHIPS:\n"
        "  price_ticks.coin_id -> coins.coin_id\n"
        "NOTES:\n"
        "  - price_ticks is a TIME SERIES: one row per coin per crawl, keyed by captured_at.\n"
        "  - The LATEST snapshot is the rows where captured_at = (SELECT MAX(captured_at) FROM price_ticks).\n"
        "  - For a coin's price history, filter by coin_id and ORDER BY captured_at.\n"
        "  - price_usd is the USD price; price_change_pct_24h is the 24h % change.\n"
        "  - To name a coin, JOIN price_ticks to coins on coin_id (use coins.name / coins.symbol)."
    )
    return "\n\n".join(parts) + "\n\n" + relationships
