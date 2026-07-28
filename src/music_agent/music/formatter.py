"""Renders a researched song into the post from PROJECT_SPEC.md.

Both destinations share one body — header, summary, facts, credits, call to
action — and differ only in how text is escaped and how links are attached:
Telegram gets inline buttons, Facebook gets the links as plain lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from music_agent.models import SongDossier

CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
#: Facebook's own cap is 63,206 characters; this is a readability limit.
FACEBOOK_LIMIT = 5000

_MARKDOWN_V2_SPECIALS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

_LINK_BUTTONS: tuple[tuple[str, str], ...] = (
    ("🎧 Spotify", "spotify_url"),
    ("▶️ YouTube", "youtube_url"),
    ("🍎 Apple Music", "apple_music_url"),
    ("🌍 Wikipedia", "wikipedia_url"),
    ("📝 מילים", "lyrics_url"),
    ("🏠 האתר הרשמי", "official_website"),
)

_DIVIDER = "—" * 12


@dataclass(frozen=True)
class TelegramPost:
    """A ready-to-send Telegram post: text, optional photo, inline buttons."""

    text: str
    photo_url: str | None = None
    buttons: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def fits_in_caption(self) -> bool:
        return len(self.text) <= CAPTION_LIMIT


@dataclass(frozen=True)
class FacebookPost:
    """A ready-to-publish Facebook post: message plus an optional photo."""

    message: str
    photo_url: str | None = None


def collect_links(dossier: SongDossier) -> tuple[tuple[str, str], ...]:
    """Label/URL pairs for every link the research actually verified."""
    links = []
    for label, attribute in _LINK_BUTTONS:
        url = getattr(dossier, attribute, None)
        if url and str(url).startswith(("http://", "https://")):
            links.append((label, str(url)))
    return tuple(links)


class PostFormatter:
    """Builds the Telegram post body for a given parse mode."""

    def __init__(self, parse_mode: str = "HTML") -> None:
        if parse_mode not in {"HTML", "MarkdownV2"}:
            raise ValueError("parse_mode must be 'HTML' or 'MarkdownV2'")
        self._parse_mode = parse_mode

    def format(self, dossier: SongDossier) -> TelegramPost:
        sections = _compose(dossier, escape=self._escape, bold=self._bold)
        return TelegramPost(
            text=_truncate("\n\n".join(sections), MESSAGE_LIMIT),
            photo_url=dossier.album_cover_url,
            buttons=collect_links(dossier),
        )

    def _escape(self, value: str) -> str:
        if self._parse_mode == "HTML":
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return _MARKDOWN_V2_SPECIALS.sub(r"\\\1", value)

    def _bold(self, value: str) -> str:
        return f"<b>{value}</b>" if self._parse_mode == "HTML" else f"*{value}*"


class FacebookPostFormatter:
    """Builds the Facebook post: plain text with the links spelled out."""

    def format(self, dossier: SongDossier) -> FacebookPost:
        sections = _compose(dossier, escape=_identity, bold=_identity)

        links = collect_links(dossier)
        if links:
            sections += [
                _DIVIDER,
                "\n".join(f"{label}: {url}" for label, url in links),
            ]

        return FacebookPost(
            message=_truncate("\n\n".join(sections), FACEBOOK_LIMIT),
            photo_url=dossier.album_cover_url,
        )


def _compose(
    dossier: SongDossier,
    *,
    escape: Callable[[str], str],
    bold: Callable[[str], str],
) -> list[str]:
    """The shared post body, in the order defined by the spec's template."""
    divider = escape(_DIVIDER)

    header = [
        f"🎵 {bold('שיר היום')}",
        "",
        f"🎤 {bold(escape(dossier.artist))} – {bold(escape(dossier.title))}",
    ]
    if dossier.album:
        header.append(f"📀 {escape(dossier.album)}")
    header.append(f"📅 {dossier.release_year}")
    if dossier.genre:
        header.append(f"⭐ {escape(dossier.genre)}")

    sections = ["\n".join(header), divider, escape(dossier.summary_he.strip())]

    facts = [
        f"{index}. {escape(fact.text)}"
        for index, fact in enumerate(dossier.facts[:3], start=1)
    ]
    if facts:
        sections += [divider, f"💡 {bold('הידעת?')}", "\n".join(facts)]

    credits = []
    if dossier.songwriters:
        credits.append(f"✍️ {escape('כתיבה')}: {escape(dossier.songwriters)}")
    if dossier.producer:
        credits.append(f"🎚️ {escape('הפקה')}: {escape(dossier.producer)}")
    if credits:
        sections += [divider, "\n".join(credits)]

    sections += [divider, escape("מה דעתכם על השיר? 👇")]
    return sections


def _identity(value: str) -> str:
    return value


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
