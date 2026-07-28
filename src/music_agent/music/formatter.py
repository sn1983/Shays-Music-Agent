"""Renders a researched song into the Telegram post from PROJECT_SPEC.md."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from music_agent.models import SongDossier

CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096

_MARKDOWN_V2_SPECIALS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

_LINK_BUTTONS: tuple[tuple[str, str], ...] = (
    ("🎧 Spotify", "spotify_url"),
    ("▶️ YouTube", "youtube_url"),
    ("🍎 Apple Music", "apple_music_url"),
    ("🌍 Wikipedia", "wikipedia_url"),
    ("📝 מילים", "lyrics_url"),
    ("🏠 האתר הרשמי", "official_website"),
)


@dataclass(frozen=True)
class TelegramPost:
    """A ready-to-send post: text, optional photo, and inline link buttons."""

    text: str
    photo_url: str | None = None
    buttons: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def fits_in_caption(self) -> bool:
        return len(self.text) <= CAPTION_LIMIT


class PostFormatter:
    """Builds the post body for a given Telegram parse mode."""

    def __init__(self, parse_mode: str = "HTML") -> None:
        if parse_mode not in {"HTML", "MarkdownV2"}:
            raise ValueError("parse_mode must be 'HTML' or 'MarkdownV2'")
        self._parse_mode = parse_mode

    def format(self, dossier: SongDossier) -> TelegramPost:
        esc = self._escape
        bold = self._bold
        divider = self._escape("—" * 12)

        header = [
            f"🎵 {bold('שיר היום')}",
            "",
            f"🎤 {bold(esc(dossier.artist))} – {bold(esc(dossier.title))}",
        ]
        if dossier.album:
            header.append(f"📀 {esc(dossier.album)}")
        header.append(f"📅 {dossier.release_year}")
        if dossier.genre:
            header.append(f"⭐ {esc(dossier.genre)}")

        facts = [
            f"{index}. {esc(fact.text)}"
            for index, fact in enumerate(dossier.facts[:3], start=1)
        ]

        sections = [
            "\n".join(header),
            divider,
            esc(dossier.summary_he.strip()),
        ]
        if facts:
            sections += [divider, f"💡 {bold('הידעת?')}", "\n".join(facts)]

        credits = self._credits(dossier)
        if credits:
            sections += [divider, credits]

        sections += [divider, esc("מה דעתכם על השיר? 👇")]

        text = "\n\n".join(sections)
        return TelegramPost(
            text=_truncate(text, MESSAGE_LIMIT),
            photo_url=dossier.album_cover_url,
            buttons=self._buttons(dossier),
        )

    # ------------------------------------------------------------------ #

    def _credits(self, dossier: SongDossier) -> str:
        lines = []
        if dossier.songwriters:
            lines.append(f"✍️ {self._escape('כתיבה')}: {self._escape(dossier.songwriters)}")
        if dossier.producer:
            lines.append(f"🎚️ {self._escape('הפקה')}: {self._escape(dossier.producer)}")
        return "\n".join(lines)

    @staticmethod
    def _buttons(dossier: SongDossier) -> tuple[tuple[str, str], ...]:
        buttons = []
        for label, attribute in _LINK_BUTTONS:
            url = getattr(dossier, attribute, None)
            if url and str(url).startswith(("http://", "https://")):
                buttons.append((label, str(url)))
        return tuple(buttons)

    def _escape(self, value: str) -> str:
        if self._parse_mode == "HTML":
            return (
                value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
        return _MARKDOWN_V2_SPECIALS.sub(r"\\\1", value)

    def _bold(self, value: str) -> str:
        return f"<b>{value}</b>" if self._parse_mode == "HTML" else f"*{value}*"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
