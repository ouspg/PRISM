"""Database engine, session factory, and schema initialization."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger("prism.db")

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine(database_url: str | None = None) -> Engine:
    """Create or return the singleton SQLAlchemy engine."""
    global _engine
    if _engine is not None:
        return _engine

    if database_url is None:
        from prism.settings import Settings

        database_url = Settings().database_url

    _engine = create_engine(
        database_url,
        pool_size=5,
        pool_pre_ping=True,
        echo=False,
    )
    return _engine


def get_session(engine: Engine | None = None) -> Session:
    """Create a new database session."""
    global _SessionFactory
    if _SessionFactory is None:
        if engine is None:
            engine = get_engine()
        _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory()


def init_db(engine: Engine | None = None, sql_path: Path | None = None) -> None:
    """Execute sql/001_init.sql against the database.

    Skips gracefully if tables/types already exist.
    """
    if engine is None:
        engine = get_engine()

    if sql_path is None:
        from prism.settings import Settings

        sql_path = Settings().sql_init_path

    sql_text = sql_path.read_text(encoding="utf-8")

    with engine.begin() as conn:
        # Execute each statement in its own savepoint so that a failure
        # (e.g. CREATE TYPE without IF NOT EXISTS) doesn't abort the
        # entire transaction.
        for statement in _split_sql_statements(sql_text):
            statement = statement.strip()
            if not statement:
                continue
            try:
                nested = conn.begin_nested()  # SAVEPOINT
                conn.execute(text(statement))
                nested.commit()
            except Exception as exc:
                nested.rollback()
                err_msg = str(exc).lower()
                if "already exists" in err_msg:
                    log.debug("Skipping (already exists): %s...", statement[:60])
                else:
                    raise

    log.info("Database schema initialized from %s", sql_path.name)


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script on semicolons, respecting basic quoting."""
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_dollar_quote = False

    for char in sql:
        if char == "'" and not in_dollar_quote:
            in_single_quote = not in_single_quote
        elif char == "$" and not in_single_quote:
            # Simplified: toggle on $$
            in_dollar_quote = not in_dollar_quote
        elif char == ";" and not in_single_quote and not in_dollar_quote:
            statements.append("".join(current))
            current = []
            continue
        current.append(char)

    # Last statement (no trailing semicolon)
    remaining = "".join(current).strip()
    if remaining:
        statements.append(remaining)

    return statements
