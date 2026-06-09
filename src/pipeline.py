"""End-to-end glue: NL question -> SQL -> safe execution -> result.

Kept UI-agnostic so it can be called from Streamlit, a test, or a notebook.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.db.introspect import schema_context
from src.llm.base import LLMProvider
from src.llm.prompt import SYSTEM_PROMPT, build_user_prompt, extract_sql
from src.safety.executor import run_query


@dataclass
class QueryResult:
    question: str
    sql: str
    df: pd.DataFrame
    row_count: int
    explanation: str | None = None   # filled on demand by explain_sql()


def generate_sql(provider: LLMProvider, question: str) -> str:
    schema = schema_context()
    user_prompt = build_user_prompt(schema, question)
    raw = provider.complete(SYSTEM_PROMPT, user_prompt)
    return extract_sql(raw)


def answer(provider: LLMProvider, question: str) -> QueryResult:
    """Run the full pipeline. Safety errors propagate from run_query."""
    sql = generate_sql(provider, question)
    df = run_query(sql)
    return QueryResult(question=question, sql=sql, df=df, row_count=len(df))


_EXPLAIN_SYSTEM = (
    "You explain SQL to a non-technical business user in 2-3 short sentences. "
    "Say what the query returns and how, in plain language. No code, no markdown."
)


def explain_sql(provider: LLMProvider, question: str, sql: str) -> str:
    """Ask the LLM for a plain-language explanation of a generated query."""
    user = (
        f"Original question: {question}\n\n"
        f"SQL:\n{sql}\n\n"
        "Explain what this query does, briefly."
    )
    return provider.complete(_EXPLAIN_SYSTEM, user).strip()
