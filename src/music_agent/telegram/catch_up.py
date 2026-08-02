"""Giving a latecomer the song that was already published today.

Without this, someone who subscribes at 21:00 gets a welcome message and then
silence until the following evening — the worst possible first impression, and
the most likely moment for them to leave. The published post is rebuilt from
the dossier stored alongside the song, so the latecomer sees exactly what
everyone else saw a few hours earlier.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from music_agent.database.repository import SongRepository
from music_agent.models import SongDossier
from music_agent.music.formatter import PostFormatter
from music_agent.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger(__name__)


class DailyCatchUp:
    """Replays today's already-published songs to a single chat."""

    def __init__(
        self,
        telegram: TelegramClient,
        repository: SongRepository,
        *,
        timezone: str,
        parse_mode: str = "HTML",
        intro: Optional[str] = None,
    ) -> None:
        self._telegram = telegram
        self._repository = repository
        self._timezone = timezone
        self._formatter = PostFormatter(parse_mode)
        self._intro = intro

    def send_to(self, chat_id: str) -> int:
        """Send whatever was published today. Returns how many songs were sent.

        Never raises: this runs inside the subscription handler, and failing to
        deliver a bonus message must not cost the subscriber their welcome or
        their place on the list.
        """
        try:
            songs = self._repository.published_on(
                datetime.now(ZoneInfo(self._timezone)).date()
            )
        except Exception as exc:  # pragma: no cover - a corrupt database only
            logger.warning("Could not read today's songs for %s: %s", chat_id, exc)
            return 0

        sent = 0
        for song in songs:
            if not song.dossier_json:
                # Published before the dossier was kept; there is nothing to
                # rebuild the post from, so stay silent rather than guess.
                continue
            try:
                dossier = SongDossier.model_validate_json(song.dossier_json)
            except ValueError as exc:
                logger.warning("Stored dossier for %s is unreadable: %s", song.song_id, exc)
                continue

            try:
                if not sent and self._intro:
                    self._telegram.send_text(self._intro, chat_id)
                self._telegram.send_post(self._formatter.format(dossier), chat_id)
            except TelegramError as exc:
                logger.warning("Could not send today's song to %s: %s", chat_id, exc)
                break
            sent += 1

        if sent:
            logger.info("Sent %d song(s) already published today to %s.", sent, chat_id)
        return sent


__all__ = ["DailyCatchUp"]
