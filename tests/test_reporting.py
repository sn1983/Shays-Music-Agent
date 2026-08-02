"""The Markdown snapshot of the subscriber list."""

from __future__ import annotations

from datetime import datetime

import pytest

from music_agent.models import Subscriber
from music_agent.reporting import (
    REPORT_FILENAME,
    mask_chat_id,
    render_subscriber_report,
    write_subscriber_report,
)

NOW = datetime(2026, 8, 2, 13, 32)


def person(chat_id: str, **overrides) -> Subscriber:
    defaults = dict(chat_id=chat_id, joined_at="2026-08-02T10:18:29+00:00")
    defaults.update(overrides)
    return Subscriber(**defaults)


def test_active_subscribers_are_listed_with_their_join_date():
    report = render_subscriber_report(
        [person("738353373", first_name="Einav")], generated_at=NOW
    )

    assert "מנויים פעילים: **1**" in report
    assert "Einav" in report
    assert "02/08/2026" in report


def test_a_username_is_preferred_over_a_first_name():
    report = render_subscriber_report(
        [person("111222333", first_name="Dana", username="dana_k")], generated_at=NOW
    )

    assert "@dana_k" in report
    assert "Dana" not in report


def test_people_who_left_are_kept_in_a_separate_section():
    report = render_subscriber_report(
        [
            person("738353373", first_name="Einav"),
            person(
                "771002200",
                first_name="Yossi",
                is_subscribed=False,
                unsubscribed_at="2026-08-02T12:00:00+00:00",
            ),
        ],
        generated_at=NOW,
    )

    assert "מנויים פעילים: **1**" in report
    assert "נרשמו אי פעם: **2**" in report
    assert "## הוסרו מהתפוצה" in report
    assert "Yossi" in report


def test_the_owner_row_is_labelled_even_without_a_name():
    # The chat carried over from TELEGRAM_CHAT_ID never sent /start, so Telegram
    # never reported a name for it.
    report = render_subscriber_report(
        [person("780656274")], generated_at=NOW, owner_chat_id="780656274"
    )

    assert "בעל הבוט" in report


def test_an_empty_list_still_produces_a_readable_file():
    report = render_subscriber_report([], generated_at=NOW)

    assert "עדיין אין מנויים פעילים" in report
    assert "מנויים פעילים: **0**" in report


@pytest.mark.parametrize(
    "chat_id, expected",
    [
        ("738353373", "738***373"),
        ("-1001234567890", "-100***890"),
        ("12345", "*****"),
    ],
)
def test_chat_ids_are_masked(chat_id, expected):
    # The file is committed to the repository; a full id plus a first name
    # identifies a real person.
    assert mask_chat_id(chat_id) == expected


def test_the_full_chat_id_never_reaches_the_file():
    report = render_subscriber_report(
        [person("738353373", first_name="Einav")], generated_at=NOW
    )

    assert "738353373" not in report


def test_the_report_is_written_next_to_the_database(tmp_path):
    path = write_subscriber_report(
        tmp_path, [person("738353373", first_name="Einav")], generated_at=NOW
    )

    assert path == tmp_path / REPORT_FILENAME
    assert "Einav" in path.read_text(encoding="utf-8")


def test_rewriting_replaces_the_previous_snapshot(tmp_path):
    write_subscriber_report(tmp_path, [person("111", first_name="First")], generated_at=NOW)
    path = write_subscriber_report(
        tmp_path, [person("222", first_name="Second")], generated_at=NOW
    )

    content = path.read_text(encoding="utf-8")
    assert "Second" in content
    assert "First" not in content
