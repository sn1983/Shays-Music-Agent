from __future__ import annotations

from datetime import date

import pytest

from music_agent.models import PublishedSong, SongDossier, SongFact, make_song_id


@pytest.fixture
def dossier() -> SongDossier:
    return SongDossier(
        artist="Natalie Imbruglia",
        title="Torn",
        album="Left of the Middle",
        release_year=1997,
        genre="Pop Rock",
        songwriters="Scott Cutler, Anne Preven, Phil Thornalley",
        producer="Phil Thornalley",
        album_cover_url="https://example.com/cover.jpg",
        spotify_url="https://open.spotify.com/track/example",
        youtube_url="https://www.youtube.com/watch?v=example",
        apple_music_url=None,
        wikipedia_url="https://en.wikipedia.org/wiki/Torn",
        official_website=None,
        lyrics_url=None,
        summary_he="שיר שכולם זוכרים מהרדיו של סוף שנות התשעים, עם גיטרה נקייה ומלודיה שנדבקת.",
        facts=[
            SongFact(text="השיר הוקלט במקור על ידי להקה אחרת.", source="https://example.com/1"),
            SongFact(text="הקליפ צולם באולפן צילום בלונדון.", source=None),
            SongFact(text="השיר שהה שבועות רבים במצעדים.", source="https://example.com/3"),
        ],
    )


def published(artist: str, title: str, year: int, decade: str, day: str) -> PublishedSong:
    return PublishedSong(
        song_id=make_song_id(artist, title),
        artist=artist,
        title=title,
        release_year=year,
        decade=decade,
        date_published=date.fromisoformat(day),
    )
