"""Run guarded SQL as the read-only role, with a row cap and a timeout."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from src.config import MAX_RESULT_ROWS, STATEMENT_TIMEOUT_MS
from src.db.connection import readonly_engine
from src.safety.guard import ensure_safe


def run_query(sql: str) -> pd.DataFrame:
    """Validate, then execute on a read-only connection. Returns a DataFrame.

    The query is wrapped in an outer LIMIT so a missing/huge result set can't
    flood the UI, and a per-session statement_timeout bounds runtime.
    """
    safe_sql = ensure_safe(sql)
    wrapped = f"SELECT * FROM (\n{safe_sql}\n) AS _q LIMIT {MAX_RESULT_ROWS}"

    engine = readonly_engine()
    with engine.connect() as conn:
        conn.execute(text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        # Read-only transaction — a final belt over the read-only role.
        conn.execute(text("SET TRANSACTION READ ONLY"))
        return pd.read_sql(text(wrapped), conn)
