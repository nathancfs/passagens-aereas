"""SQLite price history, minimum tracking, and subscription management."""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import PriceRecord, Subscription

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id          TEXT NOT NULL,
                origin           TEXT NOT NULL,
                destination      TEXT NOT NULL,
                date_from        TEXT NOT NULL,
                date_to          TEXT NOT NULL,
                max_stops        INTEGER NOT NULL DEFAULT 1,
                currency         TEXT NOT NULL DEFAULT 'BRL',
                trip_type        TEXT NOT NULL DEFAULT 'one-way',
                return_date_from TEXT,
                return_date_to   TEXT,
                active           INTEGER NOT NULL DEFAULT 1,
                created_at       TEXT NOT NULL
            )
        """)
        # Migrate existing DBs that are missing the new columns
        for col, definition in [
            ("trip_type",        "TEXT NOT NULL DEFAULT 'one-way'"),
            ("return_date_from", "TEXT"),
            ("return_date_to",   "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE subscriptions ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass  # column already exists


# ── Price records ──────────────────────────────────────────────────────────────

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


def get_price_stats(route_key: str, departure_date: date, lookback_days: int = 60) -> dict | None:
    """Returns price statistics over the lookback window, sorted ascending. None if no history."""
    cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT price FROM price_records
            WHERE route_key = ? AND departure_date = ? AND recorded_at >= ?
            ORDER BY price ASC
            """,
            (route_key, departure_date.isoformat(), cutoff),
        ).fetchall()
    if not rows:
        return None
    prices = [r["price"] for r in rows]
    return {
        "min": prices[0],
        "max": prices[-1],
        "mean": sum(prices) / len(prices),
        "count": len(prices),
        "prices": prices,
    }


# ── Subscriptions ──────────────────────────────────────────────────────────────

def save_subscription(sub: Subscription) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO subscriptions
                (chat_id, origin, destination, date_from, date_to,
                 max_stops, currency, trip_type, return_date_from, return_date_to,
                 active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sub.chat_id,
                sub.origin,
                sub.destination,
                sub.date_from.isoformat(),
                sub.date_to.isoformat(),
                sub.max_stops,
                sub.currency,
                sub.trip_type,
                sub.return_date_from.isoformat() if sub.return_date_from else None,
                sub.return_date_to.isoformat() if sub.return_date_to else None,
                int(sub.active),
                sub.created_at.isoformat(),
            ),
        )
        return cursor.lastrowid


def get_subscriptions(chat_id: str | None = None, active_only: bool = True) -> list[Subscription]:
    with _connect() as conn:
        conditions: list[str] = []
        params: list = []
        if chat_id:
            conditions.append("chat_id = ?")
            params.append(chat_id)
        if active_only:
            conditions.append("active = 1")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM subscriptions {where} ORDER BY created_at DESC",
            params,
        ).fetchall()
    return [_row_to_subscription(r) for r in rows]


def delete_subscription(sub_id: int) -> None:
    """Soft delete."""
    with _connect() as conn:
        conn.execute("UPDATE subscriptions SET active = 0 WHERE id = ?", (sub_id,))


def _row_to_subscription(row: sqlite3.Row) -> Subscription:
    return Subscription(
        id=row["id"],
        chat_id=row["chat_id"],
        origin=row["origin"],
        destination=row["destination"],
        date_from=date.fromisoformat(row["date_from"]),
        date_to=date.fromisoformat(row["date_to"]),
        max_stops=row["max_stops"],
        currency=row["currency"],
        trip_type=row["trip_type"],
        return_date_from=date.fromisoformat(row["return_date_from"]) if row["return_date_from"] else None,
        return_date_to=date.fromisoformat(row["return_date_to"]) if row["return_date_to"] else None,
        active=bool(row["active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
