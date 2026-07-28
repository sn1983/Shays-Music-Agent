from __future__ import annotations

from collections import Counter

from conftest import published

from music_agent.models import decade_of
from music_agent.music.selector import (
    ARTIST_COOLDOWN_POSTS,
    DecadePlanner,
    build_plan,
    is_genre_allowed,
)


def test_decade_of_maps_years_to_spec_decades():
    assert decade_of(1997) == "90s"
    assert decade_of(2005) == "2000s"
    assert decade_of(2014) == "2010s"
    assert decade_of(2023) == "2020s"


def test_planner_starts_with_a_heavily_weighted_decade():
    assert DecadePlanner().next_decade(Counter()) in {"90s", "2000s"}


def test_planner_targets_the_decade_furthest_below_its_share():
    # 2010s should hold ~20% but holds none of the ten posts so far.
    counts = Counter({"90s": 5, "2000s": 3, "2020s": 2})
    assert DecadePlanner().next_decade(counts) == "2010s"


def test_planner_moves_off_an_over_represented_decade():
    counts = Counter({"90s": 9, "2000s": 0, "2010s": 0, "2020s": 0})
    assert DecadePlanner().next_decade(counts) != "90s"


def test_plan_blocks_recent_artists_and_years():
    history = [
        published("Coldplay", "Yellow", 2000, "2000s", "2026-07-20"),
        published("Travis", "Sing", 2001, "2000s", "2026-07-19"),
    ]
    plan = build_plan(history, Counter({"2000s": 2}))

    assert "Coldplay" in plan.blocked_artists
    assert "Travis" in plan.blocked_artists
    assert 2000 in plan.blocked_years
    assert "Coldplay — Yellow (2000)" in plan.recent_songs


def test_plan_limits_the_artist_cooldown_window():
    history = [
        published(f"Artist {index}", f"Song {index}", 1995, "90s", "2026-07-01")
        for index in range(ARTIST_COOLDOWN_POSTS + 10)
    ]
    plan = build_plan(history, Counter({"90s": len(history)}))
    assert len(plan.blocked_artists) == ARTIST_COOLDOWN_POSTS


def test_prompt_section_is_readable_when_history_is_empty():
    section = build_plan([], Counter()).as_prompt_section()
    assert "(none yet)" in section
    assert "TARGET DECADE" in section


def test_blocked_genres_are_rejected():
    assert is_genre_allowed("Pop Rock")
    assert is_genre_allowed(None)
    assert not is_genre_allowed("Hip Hop / Rap")
    assert not is_genre_allowed("Death Metal")
