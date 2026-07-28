"""Selection policy: which decade to target and what must be avoided.

The policy is deterministic and lives in code rather than in the prompt, so the
decade distribution and the anti-repetition rules are testable and cannot drift
with the model's mood.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from music_agent.models import DECADES, PublishedSong

# Target distribution from PROJECT_SPEC.md.
DECADE_WEIGHTS: dict[str, float] = {
    "90s": 0.30,
    "2000s": 0.30,
    "2010s": 0.20,
    "2020s": 0.20,
}

BLOCKED_GENRES: tuple[str, ...] = (
    "rap",
    "hip hop",
    "hip-hop",
    "metal",
    "death metal",
    "hardcore",
    "jazz",
    "classical",
)

PREFERRED_GENRES: tuple[str, ...] = (
    "Pop",
    "Pop Rock",
    "Rock",
    "Soft Rock",
    "Dance Pop",
    "Euro Pop",
    "Adult Contemporary",
    "Alternative Rock",
    "Synth Pop",
    "Indie Pop",
)

#: An artist may not return until this many posts have gone out.
ARTIST_COOLDOWN_POSTS = 30
#: A release year may not repeat within this window of posts.
YEAR_COOLDOWN_POSTS = 10


@dataclass(frozen=True)
class SelectionPlan:
    """The constraints handed to the model for today's pick."""

    target_decade: str
    blocked_artists: tuple[str, ...] = ()
    blocked_years: tuple[int, ...] = ()
    recent_songs: tuple[str, ...] = ()
    decade_counts: Counter[str] = field(default_factory=Counter)

    def as_prompt_section(self) -> str:
        """Render the plan as the constraint block of the selection prompt."""
        published = [f"  - {entry}" for entry in self.recent_songs] or ["  (none yet)"]
        artists = [f"  - {artist}" for artist in self.blocked_artists] or ["  (none)"]
        years = ", ".join(str(year) for year in self.blocked_years) or "(none)"
        lines = [
            f"TARGET DECADE (mandatory): {self.target_decade}",
            "",
            "ALREADY PUBLISHED — never choose any of these songs again:",
            *published,
            "",
            "ARTISTS ON COOLDOWN — do not choose any song by these artists:",
            *artists,
            "",
            "RELEASE YEARS USED RECENTLY — avoid these years:",
            f"  {years}",
        ]
        return "\n".join(lines)


class DecadePlanner:
    """Chooses the decade whose published share lags furthest behind target."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or DECADE_WEIGHTS

    def next_decade(self, counts: Counter[str]) -> str:
        total = sum(counts.get(decade, 0) for decade in DECADES)
        if total == 0:
            return max(self._weights, key=lambda decade: self._weights[decade])

        def deficit(decade: str) -> float:
            expected = self._weights.get(decade, 0.0) * (total + 1)
            return expected - counts.get(decade, 0)

        # Ties resolve by the spec's own decade ordering, keeping runs reproducible.
        return max(DECADES, key=lambda decade: (deficit(decade), -DECADES.index(decade)))


def build_plan(history: list[PublishedSong], counts: Counter[str]) -> SelectionPlan:
    """Turn publication history into the constraint set for the next pick."""
    planner = DecadePlanner()
    recent_for_artists = history[:ARTIST_COOLDOWN_POSTS]
    recent_for_years = history[:YEAR_COOLDOWN_POSTS]

    blocked_artists = tuple(dict.fromkeys(song.artist for song in recent_for_artists))
    blocked_years = tuple(dict.fromkeys(song.release_year for song in recent_for_years))
    recent_songs = tuple(
        f"{song.artist} — {song.title} ({song.release_year})" for song in history[:60]
    )

    return SelectionPlan(
        target_decade=planner.next_decade(counts),
        blocked_artists=blocked_artists,
        blocked_years=blocked_years,
        recent_songs=recent_songs,
        decade_counts=counts,
    )


def is_genre_allowed(genre: str | None) -> bool:
    """Reject the genres the spec rules out, unless explicitly asked otherwise."""
    if not genre:
        return True
    lowered = genre.lower()
    return not any(blocked in lowered for blocked in BLOCKED_GENRES)
