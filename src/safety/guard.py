"""Static SQL guard — reject anything that isn't a single, read-only SELECT.

This is the first of the two safety layers (the second is the read-only DB role).
The LLM is never trusted; this runs on its output before it touches the database.
"""

from __future__ import annotations

import sqlparse
from sqlparse.sql import Statement

# Any of these appearing as a token type or keyword means "not read-only".
_FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "COPY", "MERGE", "CALL", "EXECUTE",
    "VACUUM", "ANALYZE", "REINDEX", "COMMENT", "REFRESH",
}


class UnsafeSQLError(ValueError):
    """Raised when generated SQL fails the safety guard."""


def _allowed_start(stmt: Statement) -> bool:
    """A safe statement starts with SELECT or WITH (CTE) — nothing else."""
    for token in stmt.tokens:
        if token.is_whitespace or token.ttype in (
            sqlparse.tokens.Comment,
            sqlparse.tokens.Comment.Single,
            sqlparse.tokens.Comment.Multiline,
        ):
            continue
        return token.normalized.upper() in ("SELECT", "WITH")
    return False


def ensure_safe(sql: str) -> str:
    """Return the SQL unchanged if safe; raise UnsafeSQLError otherwise."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty SQL.")

    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        raise UnsafeSQLError(
            f"Expected exactly one statement, got {len(statements)} "
            "(multi-statement input is blocked)."
        )

    stmt = statements[0]
    if not _allowed_start(stmt):
        raise UnsafeSQLError("Only SELECT / WITH…SELECT queries are allowed.")

    # Scan every keyword token for a forbidden verb (defends against e.g.
    # a SELECT that smuggles a writable construct inside).
    for token in stmt.flatten():
        if token.ttype in sqlparse.tokens.Keyword and token.normalized.upper() in _FORBIDDEN:
            raise UnsafeSQLError(f"Forbidden keyword '{token.normalized}' in query.")

    return sql.strip()
