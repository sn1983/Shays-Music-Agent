"""SQLite persistence: duplicate protection and post analytics."""

from __future__ import annotations

import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator, Optional

from music_agent.models import PublishedSong

_SCHEMA = """
CREATE TABLE IF NOT EXISTS published_songs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id             TEXT    NOT NULL UNIQUE,
    artist              TEXT    NOT NULL,
    title               TEXT    NOT NULL,
    album               TEXT,
    release_year        INTEGER NOT NULL,
    decade              TEXT    NOT NULL,
    genre               TEXT,
    date_published      TEXT    NOT NULL,
    telegram_message_id INTEGER,
    facebook_post_id    TEXT,
    views               INTEGER NOT NULL DEFAULT 0,
    likes               INTEGER NOT NULL DEFAULT 0,
    comments            INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_published_songs_artist ON published_songs (artist);
CREATE INDEX IF NOT EXISTS idx_published_songs_date   ON published_songs (date_published);
"""


class SongRepository:
    """Small data-access layer over the published-songs table."""

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

    def exists(self, song_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM published_songs WHERE song_id = ? LIMIT 1", (song_id,)
            ).fetchone()
        return row is not None

    def recent(self, limit: int = 40) -> list[PublishedSong]:
        """Most recently published songs, newest first."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM published_songs ORDER BY date_published DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_to_model(row) for row in rows]

    def decade_counts(self) -> Counter[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT decade, COUNT(*) AS total FROM published_songs GROUP BY decade"
            ).fetchall()
        return Counter({row["decade"]: row["total"] for row in rows})

    def published_on(self, day: date) -> list[PublishedSong]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM published_songs WHERE date_published = ?", (day.isoformat(),)
            ).fetchall()
        return [_to_model(row) for row in rows]

    def add(self, song: PublishedSong) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO published_songs (
                    song_id, artist, title, album, release_year, decade, genre,
                    date_published, telegram_message_id, facebook_post_id,
                    views, likes, comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    song.song_id,
                    song.artist,
                    song.title,
                    song.album,
                    song.release_year,
                    song.decade,
                    song.genre,
                    song.date_published.isoformat(),
                    song.telegram_message_id,
                    song.facebook_post_id,
                    song.views,
                    song.likes,
                    song.comments,
                ),
            )
        return int(cursor.lastrowid)

    def update_engagement(
        self,
        song_id: str,
        *,
        views: Optional[int] = None,
        likes: Optional[int] = None,
        comments: Optional[int] = None,
        facebook_post_id: Optional[str] = None,
    ) -> None:
        assignments: list[str] = []
        values: list[object] = []
        for column, value in (
            ("views", views),
            ("likes", likes),
            ("comments", comments),
            ("facebook_post_id", facebook_post_id),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        if not assignments:
            return
        values.append(song_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE published_songs SET {', '.join(assignments)} WHERE song_id = ?",
                values,
            )

    def total(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM published_songs").fetchone()
        return int(row["total"])


def _to_model(row: sqlite3.Row) -> PublishedSong:
    return PublishedSong(
        song_id=row["song_id"],
        artist=row["artist"],
        title=row["title"],
        album=row["album"],
        release_year=row["release_year"],
        decade=row["decade"],
        genre=row["genre"],
        date_published=date.fromisoformat(row["date_published"]),
        telegram_message_id=row["telegram_message_id"],
        facebook_post_id=row["facebook_post_id"],
        views=row["views"],
        likes=row["likes"],
        comments=row["comments"],
    )
