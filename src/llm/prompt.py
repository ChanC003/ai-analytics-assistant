"""NL2SQL prompt building + extracting clean SQL from the model's reply."""

from __future__ import annotations

import re

SYSTEM_PROMPT = """\
You are a senior data analyst that writes PostgreSQL queries.
You translate a business question into ONE valid, read-only SQL SELECT statement.

Hard rules:
- Output ONLY the SQL. No prose, no explanation, no markdown fences.
- Exactly ONE statement. It MUST be a SELECT (a leading CTE `WITH ... SELECT` is fine).
- NEVER write INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT or COPY.
- Use only the tables and columns described in the schema. Do not invent columns.
- Always alias aggregates with clear snake_case names (e.g. avg_price_usd).
- When the answer is a ranking or "top N", add ORDER BY and a LIMIT.
- The data is crypto market data crawled over time into price_ticks (a time series).
- "current" / "now" / "latest" means the most recent crawl:
  filter captured_at = (SELECT MAX(captured_at) FROM price_ticks).
- Join price_ticks to coins on coin_id to show the coin name/symbol.
- Prefer readable, simple SQL; use JOINs explicitly with ON.
"""


def build_user_prompt(schema: str, question: str) -> str:
    return (
        f"Database schema:\n\n{schema}\n\n"
        f"Question: {question}\n\n"
        "Return the SQL only."
    )


_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(raw: str) -> str:
    """Strip markdown fences / stray prose, return the bare SQL statement."""
    text = raw.strip()

    # If the model wrapped it in a ```sql ... ``` fence, take the inside.
    match = _FENCE_RE.search(text)
    if match:
        text = match.group(1).strip()

    # Drop a trailing semicolon (the executor adds its own LIMIT wrapper).
    text = text.rstrip().rstrip(";").strip()
    return text
