"""Tests for the static SQL safety guard and SQL extraction.

These cover the most security-critical, easy-to-break logic and need neither a
database nor an LLM. Run:  python -m pytest tests/test_guard.py -v
"""

import pytest

from src.llm.prompt import extract_sql
from src.safety.guard import UnsafeSQLError, ensure_safe


# ─────────────────────────── guard: allowed ───────────────────────────

@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "SELECT * FROM coins",
    "select name, price_usd from price_ticks order by price_usd desc limit 10",
    "WITH r AS (SELECT 1 AS x) SELECT x FROM r",
    "SELECT c.name, t.price_usd FROM price_ticks t "
    "JOIN coins c ON c.coin_id = t.coin_id "
    "WHERE t.captured_at = (SELECT MAX(captured_at) FROM price_ticks)",
])
def test_safe_queries_pass(sql):
    assert ensure_safe(sql) == sql.strip()


# ─────────────────────────── guard: blocked ───────────────────────────

@pytest.mark.parametrize("sql", [
    "DROP TABLE coins",
    "DELETE FROM price_ticks",
    "UPDATE coins SET name = 'x'",
    "INSERT INTO coins (coin_id) VALUES ('x')",
    "TRUNCATE price_ticks",
    "ALTER TABLE coins ADD COLUMN x int",
    "GRANT ALL ON coins TO readonly",
    "SELECT * FROM coins; DROP TABLE coins",            # multi-statement smuggle
    "SELECT 1; SELECT 2",                               # multi-statement
    "",                                                  # empty
    "   ",                                               # whitespace only
])
def test_unsafe_queries_blocked(sql):
    with pytest.raises(UnsafeSQLError):
        ensure_safe(sql)


# ─────────────────────────── extract_sql ───────────────────────────

def test_extract_strips_sql_fence():
    raw = "```sql\nSELECT 1\n```"
    assert extract_sql(raw) == "SELECT 1"


def test_extract_strips_plain_fence():
    raw = "```\nSELECT * FROM coins\n```"
    assert extract_sql(raw) == "SELECT * FROM coins"


def test_extract_strips_trailing_semicolon():
    assert extract_sql("SELECT 1;") == "SELECT 1"


def test_extract_plain_passthrough():
    assert extract_sql("  SELECT 1  ") == "SELECT 1"
