"""SQLAlchemy engine factory — owner (read/write) and read-only connections."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config import DBConfig, db_config


def _url(cfg: DBConfig, user: str, password: str) -> str:
    return f"postgresql+psycopg2://{user}:{password}@{cfg.host}:{cfg.port}/{cfg.name}"


@lru_cache(maxsize=1)
def owner_engine() -> Engine:
    """Read/write engine — used by the seeder and schema introspection."""
    cfg = db_config()
    return create_engine(_url(cfg, cfg.user, cfg.password), pool_pre_ping=True)


@lru_cache(maxsize=1)
def readonly_engine() -> Engine:
    """Least-privilege engine — used to run LLM-generated SQL."""
    cfg = db_config()
    return create_engine(
        _url(cfg, cfg.readonly_user, cfg.readonly_password),
        pool_pre_ping=True,
    )
