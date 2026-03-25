from __future__ import annotations

from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    text_content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    diff_text TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def get_latest_snapshot(conn: sqlite3.Connection, source_id: str):
    query = """
    SELECT *
    FROM snapshots
    WHERE source_id = ?
    ORDER BY id DESC
    LIMIT 1
    """
    return conn.execute(query, (source_id,)).fetchone()


def insert_snapshot(conn: sqlite3.Connection, source_id: str, fetched_at: str, content_hash: str, text_content: str) -> None:
    conn.execute(
        "INSERT INTO snapshots (source_id, fetched_at, content_hash, text_content) VALUES (?, ?, ?, ?)",
        (source_id, fetched_at, content_hash, text_content),
    )
    conn.commit()


def insert_alert(conn: sqlite3.Connection, source_id: str, created_at: str, summary: str, diff_text: str) -> None:
    conn.execute(
        "INSERT INTO alerts (source_id, created_at, summary, diff_text) VALUES (?, ?, ?, ?)",
        (source_id, created_at, summary, diff_text),
    )
    conn.commit()
