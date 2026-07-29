#!/usr/bin/env python3
"""Command line entry point for the Music Nostalgia AI Agent.

    python main.py test-telegram     # בדיקה שהבוט מדבר איתך
    python main.py test-facebook     # בדיקת החיבור לעמוד הפייסבוק
    python main.py run-once          # לבחור שיר, לחקור ולשלוח עכשיו
    python main.py run-once --dry-run
    python main.py schedule          # להישאר פעיל ולשלוח כל יום ב-POST_TIME
    python main.py history           # מה כבר פורסם
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import anthropic  # noqa: E402

from music_agent.ai.claude_client import AgentError  # noqa: E402
from music_agent.config import (  # noqa: E402
    ConfigError,
    Settings,
    load_settings,
    missing_publishing_secrets,
)
from music_agent.database.repository import SongRepository  # noqa: E402
from music_agent.facebook.client import FacebookClient, FacebookError  # noqa: E402
from music_agent.logging_setup import configure_logging  # noqa: E402
from music_agent.pipeline import DailySongPipeline, PipelineError, summarise  # noqa: E402
from music_agent.scheduler.daily import run_scheduler  # noqa: E402
from music_agent.telegram.client import TelegramClient, TelegramError  # noqa: E402

logger = logging.getLogger("music_agent.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="music-agent", description="Daily Pop/Rock nostalgia agent for Telegram."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_once = commands.add_parser("run-once", help="Publish today's song right now.")
    run_once.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the post instead of sending it to Telegram.",
    )
    run_once.add_argument(
        "--once-per-day",
        action="store_true",
        help="Do nothing if a song was already published today.",
    )
    run_once.add_argument(
        "--local-hour",
        type=int,
        default=None,
        metavar="H",
        help="Exit quietly unless the local hour (TIMEZONE) equals H. Useful for cron in UTC.",
    )

    commands.add_parser("schedule", help="Run forever and publish daily at POST_TIME.")
    commands.add_parser("test-telegram", help="Verify the bot token and chat id.")
    commands.add_parser(
        "test-facebook", help="Verify the Facebook page id and access token."
    )
    commands.add_parser("init-db", help="Create the SQLite database and tables.")
    commands.add_parser("stats", help="Show how many songs were published per decade.")

    history = commands.add_parser("history", help="List recently published songs.")
    history.add_argument("--limit", type=int, default=20)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if getattr(args, "dry_run", False):
        os.environ["DRY_RUN"] = "true"

    # Credentials are validated per command (see _require_secrets) rather than
    # at load time, so a run with nothing to do never fails on a missing key.
    try:
        settings = load_settings(require_secrets=False)
    except ConfigError as exc:
        print(f"שגיאת הגדרות: {exc}", file=sys.stderr)
        return 2

    configure_logging(settings.log_level)

    handlers = {
        "run-once": _run_once,
        "schedule": _schedule,
        "test-telegram": _test_telegram,
        "test-facebook": _test_facebook,
        "init-db": _init_db,
        "stats": _stats,
        "history": _history,
    }
    return handlers[args.command](settings, args)


def _require_secrets(settings: Settings) -> int:
    """Return a non-zero exit code (and explain) if a credential is missing."""
    missing = missing_publishing_secrets(settings)
    if not missing:
        return 0
    print(
        "חסרות הגדרות בקובץ .env (או בסודות של GitHub Actions): "
        + ", ".join(missing)
        + ". ראו docs/TELEGRAM_SETUP.md",
        file=sys.stderr,
    )
    return 2


def _run_once(settings: Settings, args: argparse.Namespace) -> int:
    # The hour guard runs before anything else: on a run that is not due there
    # is nothing to validate, nothing to send, and no reason to fail.
    if args.local_hour is not None:
        current_hour = datetime.now(ZoneInfo(settings.timezone)).hour
        if current_hour != args.local_hour:
            logger.info(
                "Local hour is %02d:00 (%s), waiting for %02d:00 — nothing to do.",
                current_hour,
                settings.timezone,
                args.local_hour,
            )
            return 0

    if code := _require_secrets(settings):
        return code

    pipeline = DailySongPipeline(settings)

    try:
        results = pipeline.run(once_per_day=args.once_per_day)
    except anthropic.AuthenticationError:
        logger.error("Claude rejected the API key. Check CLAUDE_API_KEY.")
        return 1
    except (AgentError, PipelineError, TelegramError, anthropic.AnthropicError) as exc:
        logger.error("Run failed: %s", exc)
        return 1

    if not results:
        print("כבר פורסם שיר היום — לא נשלח שוב.")
        return 0

    for result in results:
        print(summarise(result))
    return 0


def _schedule(settings: Settings, _: argparse.Namespace) -> int:
    if code := _require_secrets(settings):
        return code
    run_scheduler(settings)
    return 0


def _test_telegram(settings: Settings, _: argparse.Namespace) -> int:
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        print(
            "חסרים TELEGRAM_BOT_TOKEN או TELEGRAM_CHAT_ID בקובץ .env. "
            "ראו docs/TELEGRAM_SETUP.md שלבים 1-2.",
            file=sys.stderr,
        )
        return 2

    client = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        parse_mode=settings.telegram_parse_mode,
    )
    try:
        bot = client.get_me()
        print(f"הבוט מחובר: @{bot.get('username')} ({bot.get('first_name')})")
        sent = client.send_text("✅ הבוט של שירי הנוסטלגיה מחובר ומוכן לשלוח שיר יומי.")
        print(f"נשלחה הודעת בדיקה לצ'אט {settings.telegram_chat_id} (message_id={sent.message_id})")
    except TelegramError as exc:
        print(f"הבדיקה נכשלה: {exc}", file=sys.stderr)
        print(
            "בדקו את TELEGRAM_BOT_TOKEN ואת TELEGRAM_CHAT_ID, "
            "וודאו ששלחתם /start לבוט. פרטים ב-docs/TELEGRAM_SETUP.md",
            file=sys.stderr,
        )
        return 1
    return 0


def _test_facebook(settings: Settings, _: argparse.Namespace) -> int:
    if not (settings.facebook_page_id and settings.facebook_access_token):
        print(
            "חסרים FACEBOOK_PAGE_ID או FACEBOOK_ACCESS_TOKEN בקובץ .env. "
            "ראו docs/FACEBOOK_SETUP.md.",
            file=sys.stderr,
        )
        return 2

    if not settings.facebook_enabled:
        print(
            "פרסום לפייסבוק כבוי. הגדירו FACEBOOK_ENABLED=true בקובץ .env "
            "ומלאו FACEBOOK_PAGE_ID ו-FACEBOOK_ACCESS_TOKEN."
        )
        return 1

    client = FacebookClient(
        settings.facebook_page_id,
        settings.facebook_access_token,
        api_version=settings.facebook_api_version,
    )
    try:
        page = client.get_page()
    except FacebookError as exc:
        print(f"הבדיקה נכשלה: {exc}", file=sys.stderr)
        print(
            "ודאו שהטוקן הוא Page Access Token ארוך-טווח עם ההרשאות "
            "pages_manage_posts ו-pages_read_engagement. פרטים ב-docs/FACEBOOK_SETUP.md",
            file=sys.stderr,
        )
        return 1

    print(f"מחובר לעמוד: {page.get('name')} (id={page.get('id')})")
    print("הטוקן תקין. השיר הבא יפורסם גם לפייסבוק.")
    return 0


def _init_db(settings: Settings, _: argparse.Namespace) -> int:
    SongRepository(settings.database_path).initialize()
    print(f"מסד הנתונים מוכן: {settings.database_path}")
    return 0


def _stats(settings: Settings, _: argparse.Namespace) -> int:
    repository = SongRepository(settings.database_path)
    repository.initialize()
    counts = repository.decade_counts()
    total = repository.total()
    print(f"סה\"כ שירים שפורסמו: {total}")
    for decade in ("90s", "2000s", "2010s", "2020s"):
        count = counts.get(decade, 0)
        share = f"{(count / total * 100):.0f}%" if total else "0%"
        print(f"  {decade:>6}: {count:>3}  ({share})")
    return 0


def _history(settings: Settings, args: argparse.Namespace) -> int:
    repository = SongRepository(settings.database_path)
    repository.initialize()
    songs = repository.recent(limit=args.limit)
    if not songs:
        print("עדיין לא פורסמו שירים.")
        return 0
    for song in songs:
        print(
            f"{song.date_published} | {song.artist} – {song.title} "
            f"({song.release_year}, {song.decade})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
