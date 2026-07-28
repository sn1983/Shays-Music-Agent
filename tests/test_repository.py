from __future__ import annotations

from collections import Counter
from datetime import date

import pytest
from conftest import published

from music_agent.database.repository import SongRepository


@pytest.fixture
def repository(tmp_path) -> SongRepository:
    repository = SongRepository(tmp_path / "test.db")
    repository.initialize()
    return repository


def test_a_published_song_is_remembered(repository: SongRepository):
    song = published("Keane", "Somewhere Only We Know", 2004, "2000s", "2026-07-20")
    repository.add(song)

    assert repository.exists(song.song_id)
    assert not repository.exists("nobody::nothing")
    assert repository.total() == 1


def test_the_same_song_cannot_be_stored_twice(repository: SongRepository):
    song = published("Keane", "Somewhere Only We Know", 2004, "2000s", "2026-07-20")
    repository.add(song)
    with pytest.raises(Exception):
        repository.add(song)


def test_recent_returns_newest_first(repository: SongRepository):
    repository.add(published("A", "Old", 1995, "90s", "2026-07-01"))
    repository.add(published("B", "New", 2015, "2010s", "2026-07-20"))

    assert [song.title for song in repository.recent()] == ["New", "Old"]


def test_decade_counts_feed_the_planner(repository: SongRepository):
    repository.add(published("A", "One", 1995, "90s", "2026-07-01"))
    repository.add(published("B", "Two", 1998, "90s", "2026-07-02"))
    repository.add(published("C", "Three", 2015, "2010s", "2026-07-03"))

    assert repository.decade_counts() == Counter({"90s": 2, "2010s": 1})


def test_published_on_supports_the_once_per_day_guard(repository: SongRepository):
    repository.add(published("A", "One", 1995, "90s", "2026-07-20"))

    assert len(repository.published_on(date(2026, 7, 20))) == 1
    assert repository.published_on(date(2026, 7, 21)) == []


def test_engagement_metrics_can_be_updated(repository: SongRepository):
    song = published("A", "One", 1995, "90s", "2026-07-20")
    repository.add(song)

    repository.update_engagement(song.song_id, views=120, likes=7, facebook_post_id="fb_1")
    stored = repository.recent()[0]

    assert (stored.views, stored.likes, stored.facebook_post_id) == (120, 7, "fb_1")
    assert stored.comments == 0
