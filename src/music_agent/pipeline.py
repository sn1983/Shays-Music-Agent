"""The daily workflow: choose → research → format → publish → record."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from music_agent.ai.claude_client import AgentError, ClaudeMusicAgent
from music_agent.config import Settings
from music_agent.database.repository import SongRepository
from music_agent.facebook.client import FacebookClient, FacebookError
from music_agent.models import PublishedSong, SongDossier, SongSelection, decade_of
from music_agent.music.formatter import FacebookPostFormatter, PostFormatter, TelegramPost
from music_agent.music.selector import build_plan, is_genre_allowed
from music_agent.telegram.client import TelegramClient

logger = logging.getLogger(__name__)

MAX_SELECTION_ATTEMPTS = 4


class PipelineError(RuntimeError):
    """Raised when the daily run cannot complete."""


@dataclass(frozen=True)
class PublishResult:
    """What a single run produced."""

    selection: SongSelection
    dossier: SongDossier
    post: TelegramPost
    telegram_message_id: Optional[int]
    facebook_post_id: Optional[str] = None
    skipped_reason: Optional[str] = None

    @property
    def published(self) -> bool:
        return self.skipped_reason is None


class DailySongPipeline:
    """Wires the agent, the database, Telegram and Facebook into one run."""

    def __init__(
        self,
        settings: Settings,
        *,
        repository: Optional[SongRepository] = None,
        agent: Optional[ClaudeMusicAgent] = None,
        telegram: Optional[TelegramClient] = None,
        facebook: Optional[FacebookClient] = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or SongRepository(settings.database_path)
        self._agent = agent or ClaudeMusicAgent(
            settings.claude_api_key,
            model=settings.claude_model,
            effort=settings.claude_effort,
            fallback_model=settings.claude_fallback_model or None,
        )
        self._telegram = telegram or TelegramClient(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            parse_mode=settings.telegram_parse_mode,
        )
        self._formatter = PostFormatter(settings.telegram_parse_mode)
        self._facebook_formatter = FacebookPostFormatter()
        self._facebook = facebook or self._build_facebook_client(settings)

    @staticmethod
    def _build_facebook_client(settings: Settings) -> Optional[FacebookClient]:
        if not settings.facebook_enabled:
            return None
        return FacebookClient(
            settings.facebook_page_id,
            settings.facebook_access_token,
            api_version=settings.facebook_api_version,
        )

    @property
    def repository(self) -> SongRepository:
        return self._repository

    def now(self) -> datetime:
        return datetime.now(ZoneInfo(self._settings.timezone))

    def run(self, *, once_per_day: bool = False) -> list[PublishResult]:
        """Publish today's songs. Returns one result per song."""
        self._repository.initialize()
        today = self.now().date()

        if once_per_day and self._repository.published_on(today):
            logger.info("A song was already published on %s; nothing to do.", today)
            return []

        results: list[PublishResult] = []
        for index in range(self._settings.songs_per_day):
            if index:
                logger.info("Preparing song %d of %d.", index + 1, self._settings.songs_per_day)
            results.append(self._publish_one(today))
        return results

    # ------------------------------------------------------------------ #

    def _publish_one(self, today: date) -> PublishResult:
        selection = self._choose_song()
        logger.info(
            "Selected: %s — %s (%d, %s)",
            selection.artist,
            selection.title,
            selection.release_year,
            selection.genre,
        )

        dossier = self._agent.research_song(selection)
        post = self._formatter.format(dossier)

        if self._settings.dry_run:
            logger.info("DRY_RUN is on — not sending to Telegram.")
            print(post.text)
            if post.buttons:
                print("\nלינקים:", ", ".join(f"{label} -> {url}" for label, url in post.buttons))
            return PublishResult(
                selection=selection,
                dossier=dossier,
                post=post,
                telegram_message_id=None,
                skipped_reason="dry-run",
            )

        sent = self._telegram.send_post(post)
        logger.info("Sent to Telegram as message %s.", sent.message_id)

        facebook_post_id = self._publish_to_facebook(dossier)

        self._repository.add(
            PublishedSong(
                song_id=selection.song_id,
                artist=dossier.artist or selection.artist,
                title=dossier.title or selection.title,
                album=dossier.album,
                release_year=dossier.release_year or selection.release_year,
                decade=decade_of(dossier.release_year or selection.release_year),
                genre=dossier.genre or selection.genre,
                date_published=today,
                telegram_message_id=sent.message_id,
                facebook_post_id=facebook_post_id,
            )
        )
        return PublishResult(
            selection=selection,
            dossier=dossier,
            post=post,
            telegram_message_id=sent.message_id,
            facebook_post_id=facebook_post_id,
        )

    def _publish_to_facebook(self, dossier: SongDossier) -> Optional[str]:
        """Mirror the post to Facebook.

        Telegram is the primary channel and has already been delivered by this
        point, so a Facebook failure is logged and the run continues rather
        than losing a song that was published successfully.
        """
        if self._facebook is None:
            return None
        try:
            published = self._facebook.publish(self._facebook_formatter.format(dossier))
        except FacebookError as exc:
            logger.error("Facebook publishing failed: %s", exc)
            return None
        logger.info("Published to Facebook as post %s.", published.post_id)
        return published.post_id

    def _choose_song(self) -> SongSelection:
        """Ask for a pick until one satisfies every hard rule."""
        history = self._repository.recent(limit=60)
        plan = build_plan(history, self._repository.decade_counts())
        rejected: list[str] = []

        for attempt in range(1, MAX_SELECTION_ATTEMPTS + 1):
            current = (
                plan
                if not rejected
                else replace(plan, recent_songs=plan.recent_songs + tuple(rejected))
            )
            selection = self._agent.select_song(current)
            problem = self._validate(selection, plan.target_decade)
            if problem is None:
                return selection

            label = f"{selection.artist} — {selection.title} ({selection.release_year})"
            logger.warning("Rejected pick %s on attempt %d: %s", label, attempt, problem)
            rejected.append(f"{label} [rejected: {problem}]")

        raise PipelineError(
            f"No acceptable song after {MAX_SELECTION_ATTEMPTS} attempts. "
            f"Rejected: {'; '.join(rejected)}"
        )

    def _validate(self, selection: SongSelection, target_decade: str) -> Optional[str]:
        if self._repository.exists(selection.song_id):
            return "already published"
        if not is_genre_allowed(selection.genre):
            return f"genre {selection.genre!r} is on the blocked list"
        if selection.decade != target_decade:
            return f"decade {selection.decade} does not match target {target_decade}"
        if not 1990 <= selection.release_year <= self.now().year:
            return f"release year {selection.release_year} is outside the covered range"
        return None


def summarise(result: PublishResult) -> str:
    """One-line human summary of a run, for logs and the CLI."""
    status = "פורסם" if result.published else f"לא פורסם ({result.skipped_reason})"
    channels = []
    if result.telegram_message_id:
        channels.append("Telegram")
    if result.facebook_post_id:
        channels.append("Facebook")
    return (
        f"{status}: {result.selection.artist} – {result.selection.title} "
        f"({result.selection.release_year}) | facts={len(result.dossier.facts)} "
        f"| links={len(result.post.buttons)} | {', '.join(channels) or 'לא נשלח'}"
    )


__all__ = ["DailySongPipeline", "PipelineError", "PublishResult", "summarise"]
