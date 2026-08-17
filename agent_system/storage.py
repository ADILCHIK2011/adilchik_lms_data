"""Cloud DB sync with a local fallback queue.

`sync_to_cloud` tries Postgres first (reusing the same `DATABASE_URL` a
Prisma/NestJS backend would use against `schema.prisma`). If `DATABASE_URL`
is unset, or the connection/write fails for any reason (network blip, DB
down for maintenance, wrong credentials), the payload is written to a local
SQLite queue instead of being lost. `flush_fallback_queue` is called at the
start of every scheduled run to drain anything queued while the cloud DB was
unreachable — this is the fallback/retry logic for Agent 3's hourly sync.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .models import SyncResult

logger = logging.getLogger("agent_system.storage")

_CREATE_SQLITE_TABLE = """
CREATE TABLE IF NOT EXISTS pending_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""


def _sqlite_conn() -> sqlite3.Connection:
    settings.sqlite_fallback_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_fallback_path)
    conn.execute(_CREATE_SQLITE_TABLE)
    return conn


def _write_to_fallback_queue(payload: dict[str, Any]) -> SyncResult:
    try:
        with _sqlite_conn() as conn:
            conn.execute(
                "INSERT INTO pending_sync (created_at, payload) VALUES (?, ?)",
                (datetime.now(timezone.utc).isoformat(), json.dumps(payload, default=str)),
            )
        return SyncResult(target="sqlite_fallback", ok=True, rows_written=1)
    except sqlite3.Error as exc:
        return SyncResult(target="sqlite_fallback", ok=False, error=str(exc))


def _write_to_postgres(payload: dict[str, Any]) -> SyncResult:
    from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, Table, create_engine
    from sqlalchemy.exc import SQLAlchemyError

    metadata = MetaData()
    reports = Table(
        "lms_agent_reports",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("generated_at", DateTime),
        Column("payload", JSON),
    )
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with engine.begin() as conn:
            metadata.create_all(conn, tables=[reports])
            conn.execute(
                reports.insert().values(
                    generated_at=datetime.now(timezone.utc), payload=payload
                )
            )
        return SyncResult(target="postgres", ok=True, rows_written=1)
    except SQLAlchemyError as exc:
        logger.warning("Postgres sync muvaffaqiyatsiz, fallback navbatga yozilmoqda: %s", exc)
        return SyncResult(target="postgres", ok=False, error=str(exc))


def sync_to_cloud(payload: dict[str, Any]) -> SyncResult:
    if not settings.database_url:
        logger.info("DATABASE_URL sozlanmagan — to'g'ridan-to'g'ri fallback navbatga yozilmoqda")
        return _write_to_fallback_queue(payload)

    result = _write_to_postgres(payload)
    if result.ok:
        return result
    return _write_to_fallback_queue(payload)


def flush_fallback_queue(max_rows: int = 100) -> int:
    """Attempt to push queued rows to Postgres; returns count successfully flushed."""
    if not settings.database_url or not Path(settings.sqlite_fallback_path).exists():
        return 0

    flushed = 0
    with _sqlite_conn() as conn:
        rows = conn.execute(
            "SELECT id, payload FROM pending_sync ORDER BY id LIMIT ?", (max_rows,)
        ).fetchall()
        for row_id, payload_text in rows:
            result = _write_to_postgres(json.loads(payload_text))
            if result.ok:
                conn.execute("DELETE FROM pending_sync WHERE id = ?", (row_id,))
                flushed += 1
            else:
                break  # cloud DB still unreachable, stop trying this round
    return flushed
