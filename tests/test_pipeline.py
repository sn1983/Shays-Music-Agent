from __future__ import annotations

from datetime import date

import pytest
from conftest import published

from music_agent.config import Settings
from music_agent.database.repository import SongRepository
from music_agent.facebook.client import FacebookError, PublishedPost
from music_agent.models import SongDossier, SongSelection
from music_agent.music.formatter import TelegramPost
from music_agent.music.selector import build_plan
from music_agent.pipeline import DailySongPipeline, PipelineError
from music_agent.telegram.client import SentMessage


class FakeAgent:
    """Returns queued selections, so the pipeline's validation can be exercised."""

    def __init__(self, selections: list[SongSelection], dossier: SongDossier) -> None:
        self._selections = list(selections)
        self._dossier = dossier
        self.plans: list[object] = []

    def select_song(self, plan):
        self.plans.append(plan)
        return self._selections.pop(0)

    def research_song(self, selection):
        return self._dossier


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[TelegramPost] = []

    def send_post(self, post: TelegramPost) -> SentMessage:
        self.sent.append(post)
        return SentMessage(message_id=4242, chat_id="123")


def make_settings(tmp_path, **overrides) -> Settings:
    defaults = dict(
        claude_api_key="test-key",
        claude_model="claude-opus-5",
        claude_effort="high",
        claude_fallback_model="claude-sonnet-5",
        telegram_bot_token="test-token",
        telegram_chat_id="123",
        telegram_parse_mode="HTML",
        facebook_enabled=False,
        facebook_page_id="",
        facebook_access_token="",
        facebook_api_version="v21.0",
        database_path=tmp_path / "pipeline.db",
        timezone="Asia/Jerusalem",
        log_level="INFO",
        post_time="20:00",
        songs_per_day=1,
        dry_run=False,
    )
    defaults.update(overrides)
    return Settings(**defaults)


DECADE_YEARS = {"90s": 1995, "2000s": 2004, "2010s": 2014, "2020s": 2022}


def target_of(repository: SongRepository) -> tuple[str, int]:
    """The decade the planner will ask for next, and a year inside it."""
    plan = build_plan(repository.recent(60), repository.decade_counts())
    return plan.target_decade, DECADE_YEARS[plan.target_decade]


def selection(artist: str, title: str, year: int, genre: str = "Pop Rock") -> SongSelection:
    return SongSelection(
        artist=artist,
        title=title,
        release_year=year,
        genre=genre,
        category="big-hit",
        reason="בדיקה",
    )


@pytest.fixture
def pipeline_parts(tmp_path, dossier):
    settings = make_settings(tmp_path)
    repository = SongRepository(settings.database_path)
    repository.initialize()
    telegram = FakeTelegram()
    return settings, repository, telegram, dossier


def build(settings, repository, telegram, agent) -> DailySongPipeline:
    return DailySongPipeline(
        settings, repository=repository, agent=agent, telegram=telegram
    )


def test_a_successful_run_sends_the_post_and_records_it(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    _, year = target_of(repository)
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", year)], dossier)

    results = build(settings, repository, telegram, agent).run()

    assert len(telegram.sent) == 1
    assert results[0].published
    assert results[0].telegram_message_id == 4242

    stored = repository.recent()[0]
    assert (stored.artist, stored.title) == ("Natalie Imbruglia", "Torn")
    assert stored.telegram_message_id == 4242


def test_an_already_published_song_is_rejected_and_retried(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    repository.add(published("Oasis", "Wonderwall", 1995, "90s", "2026-07-01"))
    _, year = target_of(repository)
    agent = FakeAgent(
        [
            selection("Oasis", "Wonderwall", 1995),  # already in the database
            selection("Snow Patrol", "Run", year),
        ],
        dossier,
    )

    build(settings, repository, telegram, agent).run()

    assert len(agent.plans) == 2
    assert any("rejected: already published" in entry for entry in agent.plans[1].recent_songs)


def test_a_blocked_genre_is_rejected(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    _, year = target_of(repository)
    agent = FakeAgent(
        [
            selection("Some Rapper", "A Track", year, genre="Hip Hop"),
            selection("The Cranberries", "Dreams", year),
        ],
        dossier,
    )

    build(settings, repository, telegram, agent).run()

    assert len(telegram.sent) == 1
    assert agent.plans[1].recent_songs[-1].endswith("blocked list]")


def test_the_run_fails_loudly_when_no_pick_is_acceptable(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    agent = FakeAgent([selection("X", "Y", 1996, genre="Jazz")] * 4, dossier)

    with pytest.raises(PipelineError):
        build(settings, repository, telegram, agent).run()

    assert telegram.sent == []


def test_dry_run_neither_sends_nor_records(tmp_path, dossier, capsys):
    settings = make_settings(tmp_path, dry_run=True)
    repository = SongRepository(settings.database_path)
    repository.initialize()
    telegram = FakeTelegram()
    _, year = target_of(repository)
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", year)], dossier)

    results = build(settings, repository, telegram, agent).run()

    assert telegram.sent == []
    assert repository.total() == 0
    assert results[0].skipped_reason == "dry-run"
    assert "שיר היום" in capsys.readouterr().out


def test_once_per_day_skips_a_second_run(pipeline_parts, monkeypatch):
    settings, repository, telegram, dossier = pipeline_parts
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", 1995)], dossier)
    pipeline = build(settings, repository, telegram, agent)
    monkeypatch.setattr(SongRepository, "published_on", lambda self, day: ["already"])

    assert pipeline.run(once_per_day=True) == []
    assert telegram.sent == []


def test_the_target_decade_drives_the_next_pick(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    for index in range(4):
        repository.add(published(f"A{index}", f"S{index}", 1995, "90s", f"2026-07-0{index + 1}"))
    agent = FakeAgent([selection("The Cranberries", "Dreams", 1992)] * 4, dossier)

    with pytest.raises(PipelineError):
        build(settings, repository, telegram, agent).run()

    # Four 90s posts in a row means the planner must ask for another decade,
    # so a fifth 90s pick is rejected on every attempt.
    assert agent.plans[0].target_decade != "90s"


def test_publication_date_uses_the_configured_timezone(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    _, year = target_of(repository)
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", year)], dossier)
    pipeline = build(settings, repository, telegram, agent)

    pipeline.run()

    assert repository.recent()[0].date_published == pipeline.now().date()
    assert isinstance(repository.recent()[0].date_published, date)


# --------------------------------------------------------------------- #
# Facebook mirroring (Phase 2)
# --------------------------------------------------------------------- #


class FakeFacebook:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.published: list[object] = []

    def publish(self, post, *, publish_at=None):
        if self.error:
            raise self.error
        self.published.append(post)
        return PublishedPost(post_id="page_1_post_42")


def test_the_post_is_mirrored_to_facebook_when_enabled(tmp_path, dossier):
    settings = make_settings(tmp_path, facebook_enabled=True, facebook_page_id="page-1")
    repository = SongRepository(settings.database_path)
    repository.initialize()
    telegram, facebook = FakeTelegram(), FakeFacebook()
    _, year = target_of(repository)
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", year)], dossier)

    results = DailySongPipeline(
        settings, repository=repository, agent=agent, telegram=telegram, facebook=facebook
    ).run()

    assert len(facebook.published) == 1
    assert "🎧 Spotify: https://" in facebook.published[0].message
    assert results[0].facebook_post_id == "page_1_post_42"
    assert repository.recent()[0].facebook_post_id == "page_1_post_42"


def test_a_facebook_failure_does_not_lose_the_telegram_post(tmp_path, dossier):
    settings = make_settings(tmp_path, facebook_enabled=True, facebook_page_id="page-1")
    repository = SongRepository(settings.database_path)
    repository.initialize()
    telegram = FakeTelegram()
    facebook = FakeFacebook(error=FacebookError("Invalid OAuth access token"))
    _, year = target_of(repository)
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", year)], dossier)

    results = DailySongPipeline(
        settings, repository=repository, agent=agent, telegram=telegram, facebook=facebook
    ).run()

    assert len(telegram.sent) == 1          # Telegram still went out
    assert results[0].published             # and the run counts as successful
    assert results[0].facebook_post_id is None
    assert repository.total() == 1          # the song is still recorded as published


def test_facebook_is_skipped_when_disabled(pipeline_parts):
    settings, repository, telegram, dossier = pipeline_parts
    _, year = target_of(repository)
    agent = FakeAgent([selection("Natalie Imbruglia", "Torn", year)], dossier)

    results = build(settings, repository, telegram, agent).run()

    assert results[0].facebook_post_id is None
    assert repository.recent()[0].facebook_post_id is None
