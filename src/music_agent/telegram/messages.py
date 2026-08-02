"""The bot's conversational replies, in Hebrew.

Every reply that confirms a subscription states *when* the daily song arrives —
that is the one fact a new subscriber needs and cannot guess.
"""

from __future__ import annotations

TIMEZONE_LABELS = {
    "Asia/Jerusalem": "שעון ישראל",
}


def _clock(post_time: str, timezone: str) -> str:
    label = TIMEZONE_LABELS.get(timezone, timezone)
    return f"{post_time} ({label})"


#: Shown on the bot's profile, under its name. Telegram caps this at 120 chars.
BOT_SHORT_DESCRIPTION = "שיר פופ/רוק אחד כל יום, עם הסיפור שמאחוריו וקישורים להאזנה 🎵"


def bot_description(post_time: str, timezone: str) -> str:
    """Shown on the empty chat screen, *before* the user presses Start.

    This is the only text a new visitor sees at the moment they arrive, so it
    carries the two facts that matter: what they will get, and that the
    confirmation takes a few minutes to arrive. Telegram caps it at 512 chars.
    """
    return (
        "🎵 שיר אחד כל יום — פופ ורוק מהעשורים 90's, 2000's, 2010's ו-2020's.\n\n"
        f"בכל יום בשעה {_clock(post_time, timezone)} מגיע שיר עם תקציר בעברית, "
        "שלוש עובדות מעניינות וקישורים ל-Spotify, YouTube וויקיפדיה.\n\n"
        "לחצו START כדי להירשם. הודעת האישור מגיעה תוך כמה דקות."
    )


#: The menu Telegram shows behind the "/" button in the chat.
BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "הרשמה לשיר היומי"),
    ("stop", "הפסקת העדכונים"),
    ("status", "מצב המנוי ושעת השליחה"),
    ("help", "מה הבוט עושה"),
)


def welcome(post_time: str, timezone: str, *, first_name: str | None = None) -> str:
    """Sent the moment someone subscribes."""
    greeting = f"היי {first_name}! " if first_name else "היי! "
    return (
        f"🎵 <b>{greeting}נרשמת ל\"שיר היום\"</b>\n\n"
        f"⏰ כל יום בשעה <b>{_clock(post_time, timezone)}</b> תקבלו כאן שיר אחד — "
        "פופ או רוק מהעשורים 90's, 2000's, 2010's ו-2020's.\n\n"
        "בכל הודעה יחכו לכם:\n"
        "🎤 האמן, האלבום, השנה והסגנון\n"
        "📖 תקציר קצר בעברית על הסיפור מאחורי השיר\n"
        "💡 שלוש עובדות מעניינות\n"
        "🎧 קישורים להאזנה ב-Spotify, YouTube וויקיפדיה\n\n"
        "אף שיר לא חוזר על עצמו, ואנחנו מגוונים בין אמנים, שנים וסגנונות.\n\n"
        "📌 <b>פקודות:</b>\n"
        "/stop — להפסיק לקבל עדכונים\n"
        "/status — לבדוק את מצב המנוי\n"
        "/help — עזרה\n\n"
        "נתראה בשיר הראשון 🎶"
    )


def already_subscribed(post_time: str, timezone: str) -> str:
    return (
        "✅ אתם כבר רשומים.\n\n"
        f"השיר הבא יגיע היום בשעה <b>{_clock(post_time, timezone)}</b>.\n"
        "כדי להפסיק לקבל עדכונים: /stop"
    )


def welcome_back(post_time: str, timezone: str) -> str:
    return (
        "🎉 <b>שמחים שחזרתם!</b>\n\n"
        f"המנוי חודש — השיר הבא יגיע בשעה <b>{_clock(post_time, timezone)}</b>.\n"
        "להפסקה בכל רגע: /stop"
    )


def goodbye() -> str:
    return (
        "👋 הוסרתם מרשימת התפוצה ולא תקבלו יותר עדכונים יומיים.\n\n"
        "אם תתחרטו — פשוט שלחו /start ונחזיר אתכם."
    )


def not_subscribed() -> str:
    return "לא הייתם רשומים מלכתחילה 🙂\nכדי להירשם ולקבל שיר כל יום: /start"


def status(subscribed: bool, post_time: str, timezone: str) -> str:
    if subscribed:
        return (
            "✅ <b>המנוי פעיל.</b>\n"
            f"⏰ השיר היומי מגיע בשעה <b>{_clock(post_time, timezone)}</b>.\n\n"
            "להפסקה: /stop"
        )
    return "⛔ <b>המנוי לא פעיל.</b>\nכדי לקבל שוב שיר כל יום: /start"


def help_text(post_time: str, timezone: str) -> str:
    return (
        "🎵 <b>שיר היום</b> — שיר פופ/רוק אחד כל יום, עם הסיפור שמאחוריו "
        "וקישורים להאזנה.\n\n"
        f"⏰ שעת השליחה: <b>{_clock(post_time, timezone)}</b>\n\n"
        "📌 <b>פקודות:</b>\n"
        "/start — להירשם ולקבל עדכון יומי\n"
        "/stop — להפסיק לקבל עדכונים\n"
        "/status — מצב המנוי\n"
        "/help — ההודעה הזו"
    )
