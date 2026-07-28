from __future__ import annotations

from music_agent.models import SongDossier
from music_agent.music.formatter import MESSAGE_LIMIT, PostFormatter


def test_html_post_contains_every_template_section(dossier: SongDossier):
    post = PostFormatter("HTML").format(dossier)

    assert "🎵 <b>שיר היום</b>" in post.text
    assert "Natalie Imbruglia" in post.text
    assert "Left of the Middle" in post.text
    assert "1997" in post.text
    assert "Pop Rock" in post.text
    assert "💡 <b>הידעת?</b>" in post.text
    assert "1. " in post.text and "3. " in post.text
    assert "מה דעתכם על השיר?" in post.text


def test_links_become_inline_buttons(dossier: SongDossier):
    post = PostFormatter("HTML").format(dossier)
    labels = [label for label, _ in post.buttons]

    assert "🎧 Spotify" in labels
    assert "▶️ YouTube" in labels
    assert "🌍 Wikipedia" in labels
    # apple_music_url is None in the fixture, so it must not produce a button.
    assert "🍎 Apple Music" not in labels
    assert post.photo_url == "https://example.com/cover.jpg"


def test_html_special_characters_are_escaped(dossier: SongDossier):
    post = PostFormatter("HTML").format(dossier.model_copy(update={"album": "Rock & Roll <Live>"}))
    assert "Rock &amp; Roll &lt;Live&gt;" in post.text


def test_markdown_v2_escapes_reserved_characters(dossier: SongDossier):
    post = PostFormatter("MarkdownV2").format(
        dossier.model_copy(update={"title": "Torn (Remix) - 1997!"})
    )
    assert r"Torn \(Remix\) \- 1997\!" in post.text


def test_a_long_summary_is_truncated_to_the_telegram_limit(dossier: SongDossier):
    post = PostFormatter("HTML").format(dossier.model_copy(update={"summary_he": "א" * 6000}))
    assert len(post.text) <= MESSAGE_LIMIT
    assert not post.fits_in_caption


def test_a_short_post_fits_in_a_photo_caption(dossier: SongDossier):
    assert PostFormatter("HTML").format(dossier).fits_in_caption


def test_missing_optional_fields_are_skipped(dossier: SongDossier):
    bare = dossier.model_copy(
        update={"album": None, "genre": None, "songwriters": None, "producer": None}
    )
    post = PostFormatter("HTML").format(bare)
    assert "📀" not in post.text
    assert "⭐" not in post.text
    assert "✍️" not in post.text
