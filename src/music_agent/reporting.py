"""A human-readable snapshot of the subscriber list.

The list lives in a SQLite file, which GitHub cannot display — so a run also
writes this Markdown next to it. It is the only way to see who is subscribed
from a phone, without cloning the project.

Chat ids are masked. The file is committed to the repository, and a chat id
plus a first name identifies a real person; the full ids stay in the database
and in the local `subscribers` command.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from music_agent.models import Subscriber

REPORT_FILENAME = "subscribers.md"


def mask_chat_id(chat_id: str) -> str:
    """Keep the ends, hide the middle: 738353373 -> 738***373."""
    digits = chat_id.lstrip("-")
    if len(digits) <= 6:
        return "*" * len(digits)
    prefix = "-" if chat_id.startswith("-") else ""
    return f"{prefix}{digits[:3]}***{digits[-3:]}"


def render_subscriber_report(
    subscribers: Iterable[Subscriber],
    *,
    generated_at: datetime,
    owner_chat_id: str | None = None,
) -> str:
    people = list(subscribers)
    active = [person for person in people if person.is_subscribed]
    former = [person for person in people if not person.is_subscribed]

    lines = [
        "# 👥 מנויים",
        "",
        f"עודכן: **{generated_at:%d/%m/%Y %H:%M}**",
        "",
        f"מנויים פעילים: **{len(active)}** · נרשמו אי פעם: **{len(people)}**",
        "",
    ]

    if active:
        lines += [
            "## פעילים",
            "",
            "| # | שם | מזהה | הצטרף |",
            "|---|----|------|-------|",
        ]
        for index, person in enumerate(active, start=1):
            lines.append(
                f"| {index} | {_name(person, owner_chat_id)} | `{mask_chat_id(person.chat_id)}` "
                f"| {_date(person.joined_at)} |"
            )
        lines.append("")
    else:
        lines += ["עדיין אין מנויים פעילים.", ""]

    if former:
        lines += [
            "## הוסרו מהתפוצה",
            "",
            "| שם | מזהה | הצטרף | הוסר |",
            "|----|------|-------|------|",
        ]
        for person in former:
            lines.append(
                f"| {_name(person, owner_chat_id)} | `{mask_chat_id(person.chat_id)}` "
                f"| {_date(person.joined_at)} | {_date(person.unsubscribed_at)} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "הקובץ הזה נוצר אוטומטית בכל הרצה של הסוכן. המזהים מוצגים חלקית בכוונה — "
        "הרשימה המלאה זמינה בפקודה `python main.py subscribers`.",
    ]
    return "\n".join(lines) + "\n"


def write_subscriber_report(
    directory: Path,
    subscribers: Iterable[Subscriber],
    *,
    generated_at: datetime,
    owner_chat_id: str | None = None,
) -> Path:
    """Write the report next to the database. Returns the path written."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / REPORT_FILENAME
    path.write_text(
        render_subscriber_report(
            subscribers, generated_at=generated_at, owner_chat_id=owner_chat_id
        ),
        encoding="utf-8",
    )
    return path


def _name(person: Subscriber, owner_chat_id: str | None = None) -> str:
    if person.username:
        return f"@{person.username}"
    if person.first_name:
        return person.first_name
    # The chat carried over from TELEGRAM_CHAT_ID never sent /start, so Telegram
    # never told us a name for it.
    return "בעל הבוט" if owner_chat_id and person.chat_id == owner_chat_id else "—"


def _date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return f"{datetime.fromisoformat(value):%d/%m/%Y}"
    except ValueError:
        return value
