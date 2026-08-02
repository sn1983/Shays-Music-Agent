"""Domain models shared across the agent.

The Pydantic models double as the JSON schemas handed to the Claude API for
structured outputs, so every field is intentionally flat and nullable rather
than constrained — the structured-output schema dialect rejects constraints
such as ``minLength`` or ``minItems``.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field

# Keys the structured-output schema dialect does not accept.
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "format",
        "default",
        "examples",
    }
)

DECADES: tuple[str, ...] = ("90s", "2000s", "2010s", "2020s")


def slugify(value: str) -> str:
    """Normalise free text into a stable identifier fragment."""
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def make_song_id(artist: str, title: str) -> str:
    """Stable primary key for a song, used for duplicate protection."""
    return f"{slugify(artist)}::{slugify(title)}"


def decade_of(year: int) -> str:
    """Map a release year onto one of the decades the agent covers."""
    if year < 2000:
        return "90s"
    if year < 2010:
        return "2000s"
    if year < 2020:
        return "2010s"
    return "2020s"


class SongSelection(BaseModel):
    """Stage 1 output: which song the agent decided to publish today."""

    artist: str = Field(description="Performing artist or band, in English.")
    title: str = Field(description="Song title, in English.")
    release_year: int = Field(description="Year the song was originally released.")
    genre: str = Field(description="Main genre, e.g. Pop Rock, Dance Pop, Synth Pop.")
    category: str = Field(
        description=(
            "One of: big-hit, forgotten-hit, one-hit-wonder, hidden-gem, "
            "album-track, live-version."
        )
    )
    reason: str = Field(description="Short note (Hebrew) on why this song fits today.")

    @property
    def song_id(self) -> str:
        return make_song_id(self.artist, self.title)

    @property
    def decade(self) -> str:
        return decade_of(self.release_year)


class SongFact(BaseModel):
    """A single verified 'did you know' fact."""

    text: str = Field(description="The fact itself, written in Hebrew, 1-2 sentences.")
    source: Optional[str] = Field(
        description="URL of the source that supports this fact, or null if none."
    )


class SongDossier(BaseModel):
    """Stage 2 output: everything needed to build the Telegram post."""

    artist: str
    title: str
    album: Optional[str] = Field(description="Album name, or null if unknown.")
    release_year: int
    genre: Optional[str]
    songwriters: Optional[str] = Field(description="Comma separated, or null.")
    producer: Optional[str] = Field(description="Comma separated, or null.")
    album_cover_url: Optional[str] = Field(
        description="Direct https URL to an album cover image, or null if none was verified."
    )
    spotify_url: Optional[str]
    youtube_url: Optional[str]
    apple_music_url: Optional[str]
    wikipedia_url: Optional[str]
    official_website: Optional[str]
    lyrics_url: Optional[str]
    summary_he: str = Field(
        description="Hebrew summary, 80-150 words, radio-presenter voice, flowing prose."
    )
    facts: list[SongFact] = Field(description="Three verified interesting facts, in Hebrew.")


class Subscriber(BaseModel):
    """Someone who receives the daily song."""

    chat_id: str
    first_name: Optional[str] = None
    username: Optional[str] = None
    is_subscribed: bool = True
    joined_at: Optional[str] = None
    unsubscribed_at: Optional[str] = None
    last_error: Optional[str] = None

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.first_name or self.chat_id


class PublishedSong(BaseModel):
    """A row of the duplicate-protection / analytics database."""

    song_id: str
    artist: str
    title: str
    album: Optional[str] = None
    release_year: int
    decade: str
    genre: Optional[str] = None
    date_published: date
    telegram_message_id: Optional[int] = None
    facebook_post_id: Optional[str] = None
    views: int = 0
    likes: int = 0
    comments: int = 0


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Build an API-compatible JSON schema from a Pydantic model.

    Strips validation keywords the structured-output dialect rejects, and marks
    every object as closed with all of its properties required — optional values
    are expressed as nullable types instead of absent keys.
    """
    return _sanitise(model.model_json_schema())


def _sanitise(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitise(item) for item in node]
    if not isinstance(node, dict):
        return node

    cleaned = {
        key: _sanitise(value)
        for key, value in node.items()
        if key not in _UNSUPPORTED_SCHEMA_KEYS
    }
    if cleaned.get("type") == "object" and "properties" in cleaned:
        cleaned["additionalProperties"] = False
        cleaned["required"] = list(cleaned["properties"])
    return cleaned
