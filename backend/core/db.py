from __future__ import annotations

import logging
from pathlib import Path

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def init_pool(database_url: str, max_size: int = 20) -> ConnectionPool:
    global _pool
    _pool = ConnectionPool(
        conninfo=database_url,
        max_size=max_size,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )
    return _pool


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")
    return _pool


def query(sql: str, params: tuple = ()) -> list[dict]:
    with get_pool().connection() as conn:
        result = conn.execute(sql, params)
        return result.fetchall()  # type: ignore[return-value]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with get_pool().connection() as conn:
        result = conn.execute(sql, params)
        return result.fetchone()  # type: ignore[return-value]


def execute(sql: str, params: tuple = ()) -> None:
    with get_pool().connection() as conn:
        conn.execute(sql, params)


def execute_returning(sql: str, params: tuple = ()) -> dict:
    with get_pool().connection() as conn:
        result = conn.execute(sql, params)
        return result.fetchone()  # type: ignore[return-value]


_MIGRATION_LOCK_ID = 7438291874  # stable bigint for pg_advisory_lock


def run_migrations() -> None:
    migrations_dir = Path(__file__).parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    with get_pool().connection() as conn:
        # Serialize across Gunicorn workers: only one runs migrations at a time
        conn.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_ID,))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            for sql_file in sql_files:
                already_applied = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE filename = %s",
                    (sql_file.name,),
                ).fetchone()

                if already_applied:
                    continue

                logger.info("Applying migration: %s", sql_file.name)
                conn.execute(sql_file.read_text())
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (sql_file.name,),
                )
                logger.info("Migration applied: %s", sql_file.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_ID,))


def setup_langgraph_checkpointer() -> None:
    from langgraph.checkpoint.postgres import PostgresSaver
    with get_pool().connection() as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_ID,))
        try:
            PostgresSaver(conn).setup()  # type: ignore[arg-type]
            logger.info("LangGraph checkpointer tables ready")
        except UniqueViolation:
            logger.info("LangGraph checkpointer tables already initialised")
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_ID,))
