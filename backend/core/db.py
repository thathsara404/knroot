import logging
import os
from pathlib import Path

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation
from langgraph.checkpoint.postgres import PostgresSaver

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
        return result.fetchall()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with get_pool().connection() as conn:
        result = conn.execute(sql, params)
        return result.fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    with get_pool().connection() as conn:
        conn.execute(sql, params)


def execute_returning(sql: str, params: tuple = ()) -> dict:
    with get_pool().connection() as conn:
        result = conn.execute(sql, params)
        return result.fetchone()


def run_migrations() -> None:
    migrations_dir = Path(__file__).parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    with get_pool().connection() as conn:
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


def setup_langgraph_checkpointer() -> None:
    with get_pool().connection() as conn:
        try:
            PostgresSaver(conn).setup()
            logger.info("LangGraph checkpointer tables ready")
        except UniqueViolation:
            logger.info("LangGraph checkpointer tables already initialised")
