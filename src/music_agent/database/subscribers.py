"""Who receives the daily song, and where the Telegram update cursor is.

Subscriptions are never deleted — unsubscribing flips a flag. That keeps the
join date, lets someone re-subscribe without losing their history, and makes
"how many people left this month" answerable later.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional

from music_agent.models import Subscriber

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    chat_id         TEXT    PRIMARY KEY,
    first_name      TEXT,
    username        TEXT,
    is_subscribed   INTEGER NOT NULL DEFAULT 1,
    joined_at       TEXT    NOT NULL,
    unsubscribed_at TEXT,
    last_error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers (is_subscribed);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_UPDATE_OFFSET_KEY = "telegram_update_offset"


class SubscriptionChange(Enum):
    """What actually happened, so the bot can reply appropriately."""

    NEW = "new"
    RESUBSCRIBED = "resubscribed"
    ALREADY_SUBSCRIBED = "already_subscribed"


class SubscriberRepository:
    """Subscriber list plus the Telegram `getUpdates` cursor."""

    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    # ------------------------------------------------------------------ #
    # Subscriptions
    # ------------------------------------------------------------------ #

    def subscribe(
        self,
        chat_id: str,
        *,
        first_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> SubscriptionChange:
        existing = self.get(chat_id)
        now = _now()

        if existing is None:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO subscribers (chat_id, first_name, username, is_subscribed, joined_at)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (chat_id, first_name, username, now),
                )
            return SubscriptionChange.NEW

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE subscribers
                   SET is_subscribed = 1,
                       unsubscribed_at = NULL,
                       last_error = NULL,
                       first_name = COALESCE(?, first_name),
                       username = COALESCE(?, username)
                 WHERE chat_id = ?
                """,
                (first_name, username, chat_id),
            )
        return (
            SubscriptionChange.ALREADY_SUBSCRIBED
            if existing.is_subscribed
            else SubscriptionChange.RESUBSCRIBED
        )

    def unsubscribe(self, chat_id: str, *, reason: Optional[str] = None) -> bool:
        """Stop delivery. Returns whether they were actually subscribed."""
        existing = self.get(chat_id)
        if existing is None or not existing.is_subscribed:
            return False
        with self._connect() as connection:
            connection.execute(
                "UPDATE subscribers SET is_subscribed = 0, unsubscribed_at = ?, last_error = ? "
                "WHERE chat_id = ?",
                (_now(), reason, chat_id),
            )
        return True

    def ensure(self, chat_id: str, *, first_name: Optional[str] = None) -> bool:
        """Add a chat only if it has never been seen.

        Used to carry the original TELEGRAM_CHAT_ID into the subscriber list
        without resurrecting someone who deliberately unsubscribed.
        """
        if not chat_id or self.get(chat_id) is not None:
            return False
        self.subscribe(chat_id, first_name=first_name)
        return True

    def get(self, chat_id: str) -> Optional[Subscriber]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM subscribers WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return _to_model(row) if row else None

    def is_subscribed(self, chat_id: str) -> bool:
        subscriber = self.get(chat_id)
        return bool(subscriber and subscriber.is_subscribed)

    def active(self) -> list[Subscriber]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subscribers WHERE is_subscribed = 1 ORDER BY joined_at"
            ).fetchall()
        return [_to_model(row) for row in rows]

    def all(self) -> list[Subscriber]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subscribers ORDER BY joined_at"
            ).fetchall()
        return [_to_model(row) for row in rows]

    def counts(self) -> tuple[int, int]:
        """(active, total)."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total, "
                "COALESCE(SUM(is_subscribed), 0) AS active FROM subscribers"
            ).fetchone()
        return int(row["active"]), int(row["total"])

    # ------------------------------------------------------------------ #
    # Telegram update cursor
    # ------------------------------------------------------------------ #

    def update_offset(self) -> Optional[int]:
        """The next `getUpdates` offset, so a message is handled exactly once."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = ?", (_UPDATE_OFFSET_KEY,)
            ).fetchone()
        return int(row["value"]) if row else None

    def set_update_offset(self, offset: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO bot_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (_UPDATE_OFFSET_KEY, str(offset)),
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_model(row: sqlite3.Row) -> Subscriber:
    return Subscriber(
        chat_id=row["chat_id"],
        first_name=row["first_name"],
        username=row["username"],
        is_subscribed=bool(row["is_subscribed"]),
        joined_at=row["joined_at"],
        unsubscribed_at=row["unsubscribed_at"],
        last_error=row["last_error"],
    )
