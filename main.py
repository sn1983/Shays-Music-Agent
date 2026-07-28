#!/usr/bin/env python3
"""Command line entry point for the Music Nostalgia AI Agent.

    python main.py test-telegram     # בדיקה שהבוט מדבר איתך
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
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from music_agent.config import ConfigError, Settings, load_settings  # noqa: E402
from music_agent.database.repository import SongRepository  # noqa: E402
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
    commands.add_parser("init-db", help="Create the SQLite database and tables.")
    commands.add_parser("stats", help="Show how many songs were published per decade.")

    history = commands.add_parser("history", help="List recently published songs.")
    history.add_argument("--limit", type=int, default=20)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if getattr(args, "dry_run", False):
        os.environ["DRY_RUN"] = "true"

    needs_secrets = args.command in {"run-once", "schedule", "test-telegram"}
    try:
        settings = load_settings(require_secrets=needs_secrets)
    except ConfigError as exc:
        print(f"שגיאת הגדרות: {exc}", file=sys.stderr)
        return 2

    configure_logging(settings.log_level)

    handlers = {
        "run-once": _run_once,
        "schedule": _schedule,
        "test-telegram": _test_telegram,
        "init-db": _init_db,
        "stats": _stats,
        "history": _history,
    }
    return handlers[args.command](settings, args)


def _run_once(settings: Settings, args: argparse.Namespace) -> int:
    pipeline = DailySongPipeline(settings)

    if args.local_hour is not None:
        current_hour = pipeline.now().hour
        if current_hour != args.local_hour:
            logger.info(
                "Local hour is %02d:00 (%s), waiting for %02d:00 — nothing to do.",
                current_hour,
                settings.timezone,
                args.local_hour,
            )
            return 0

    try:
        results = pipeline.run(once_per_day=args.once_per_day)
    except (PipelineError, TelegramError) as exc:
        logger.error("Run failed: %s", exc)
        return 1

    if not results:
        print("כבר פורסם שיר היום — לא נשלח שוב.")
        return 0

    for result in results:
        print(summarise(result))
    return 0


def _schedule(settings: Settings, _: argparse.Namespace) -> int:
    run_scheduler(settings)
    return 0


def _test_telegram(settings: Settings, _: argparse.Namespace) -> int:
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
