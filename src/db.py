"""SQLite price history and minimum tracking."""

import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import PriceRecord

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_records (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                route_key     TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                price         REAL NOT NULL,
                currency      TEXT NOT NULL,
                source        TEXT NOT NULL,
                deep_link     TEXT,
                recorded_at   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_route_date
            ON price_records (route_key, departure_date)
        """)


def save_record(record: PriceRecord) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO price_records
                (route_key, departure_date, price, currency, source, deep_link, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.route_key,
                record.departure_date.isoformat(),
                record.price,
                record.currency,
                record.source,
                record.deep_link,
                record.recorded_at.isoformat(),
            ),
        )


def get_historical_min(route_key: str, departure_date: date) -> float | None:
    """Returns the lowest price ever recorded for a route+date, or None if no history."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT MIN(price) AS min_price
            FROM price_records
            WHERE route_key = ? AND departure_date = ?
            """,
            (route_key, departure_date.isoformat()),
        ).fetchone()
    return row["min_price"] if row and row["min_price"] is not None else None


def get_recent_records(route_key: str, limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM price_records
            WHERE route_key = ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (route_key, limit),
        ).fetchall()
    return [dict(r) for r in rows]
