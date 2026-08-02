"""Subscriptions: the list itself, and the /start and /stop conversation."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from music_agent.database.repository import SongRepository
from music_agent.database.subscribers import SubscriberRepository, SubscriptionChange
from music_agent.models import PublishedSong, make_song_id
from music_agent.telegram.catch_up import DailyCatchUp
from music_agent.telegram.client import TelegramError
from music_agent.telegram.subscriptions import SubscriptionService


@pytest.fixture
def subscribers(tmp_path) -> SubscriberRepository:
    repository = SubscriberRepository(tmp_path / "subs.db")
    repository.initialize()
    return repository


class FakeTelegram:
    """Replays queued updates and records the replies sent back."""

    def __init__(self, updates: list[dict] | None = None) -> None:
        self.updates = list(updates or [])
        self.replies: list[tuple[str, str]] = []  # (chat_id, text)
        self.posts: list[tuple[str, object]] = []  # (chat_id, TelegramPost)
        self.offsets: list[int | None] = []
        self.fail_for: set[str] = set()
        self.fail_posts_for: set[str] = set()

    def get_updates(self, *, offset=None, timeout=0):
        self.offsets.append(offset)
        pending, self.updates = self.updates, []
        return pending

    def send_text(self, text: str, chat_id: str | None = None):
        if chat_id in self.fail_for:
            raise TelegramError("Forbidden: bot was blocked by the user")
        self.replies.append((chat_id, text))
        return None

    def send_post(self, post, chat_id: str | None = None):
        if chat_id in self.fail_for or chat_id in self.fail_posts_for:
            raise TelegramError("Forbidden: bot was blocked by the user")
        self.posts.append((chat_id, post))
        return None


def message(update_id: int, chat_id: int, text: str, **user) -> dict:
    sender = {"id": chat_id, "is_bot": False, "first_name": "Shay"}
    sender.update(user)
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "chat": {"id": chat_id, "type": "private"},
            "from": sender,
            "text": text,
        },
    }


def service(telegram, subscribers, catch_up=None) -> SubscriptionService:
    return SubscriptionService(
        telegram,
        subscribers,
        post_time="20:00",
        timezone="Asia/Jerusalem",
        catch_up=catch_up,
    )


def songs_with_today(tmp_path, dossier, *, keep_dossier: bool = True) -> SongRepository:
    """A repository holding one song published today."""
    repository = SongRepository(tmp_path / "songs.db")
    repository.initialize()
    repository.add(
        PublishedSong(
            song_id=make_song_id(dossier.artist, dossier.title),
            artist=dossier.artist,
            title=dossier.title,
            release_year=dossier.release_year,
            decade="90s",
            date_published=datetime.now(ZoneInfo("Asia/Jerusalem")).date(),
            dossier_json=dossier.model_dump_json() if keep_dossier else None,
        )
    )
    return repository


def catch_up_for(telegram, repository) -> DailyCatchUp:
    return DailyCatchUp(
        telegram, repository, timezone="Asia/Jerusalem", intro="🎁 הנה השיר של היום:"
    )


# --------------------------------------------------------------------- #
# The subscriber list
# --------------------------------------------------------------------- #


def test_the_first_subscribe_is_new_and_the_second_is_not(subscribers):
    assert subscribers.subscribe("111") is SubscriptionChange.NEW
    assert subscribers.subscribe("111") is SubscriptionChange.ALREADY_SUBSCRIBED


def test_someone_who_left_can_come_back(subscribers):
    subscribers.subscribe("111")
    assert subscribers.unsubscribe("111")
    assert not subscribers.is_subscribed("111")

    assert subscribers.subscribe("111") is SubscriptionChange.RESUBSCRIBED
    assert subscribers.is_subscribed("111")


def test_unsubscribing_twice_is_not_an_error(subscribers):
    subscribers.subscribe("111")
    assert subscribers.unsubscribe("111")
    assert not subscribers.unsubscribe("111")


def test_only_active_subscribers_receive_posts(subscribers):
    subscribers.subscribe("111")
    subscribers.subscribe("222")
    subscribers.unsubscribe("222")

    assert [person.chat_id for person in subscribers.active()] == ["111"]
    assert len(subscribers.all()) == 2
    assert subscribers.counts() == (1, 2)


def test_the_original_chat_id_is_carried_over(subscribers):
    assert subscribers.ensure("999")
    assert subscribers.is_subscribed("999")
    # Idempotent: a second run must not duplicate or resurrect.
    assert not subscribers.ensure("999")


def test_ensure_does_not_resurrect_someone_who_left(subscribers):
    subscribers.ensure("999")
    subscribers.unsubscribe("999")

    subscribers.ensure("999")

    assert not subscribers.is_subscribed("999")


def test_the_update_offset_survives_between_runs(subscribers):
    assert subscribers.update_offset() is None
    subscribers.set_update_offset(1234)
    assert SubscriberRepository(subscribers._path).update_offset() == 1234


# --------------------------------------------------------------------- #
# The conversation
# --------------------------------------------------------------------- #


def test_start_subscribes_and_welcomes_with_the_daily_time(subscribers):
    telegram = FakeTelegram([message(1, 555, "/start")])

    report = service(telegram, subscribers).sync()

    assert subscribers.is_subscribed("555")
    chat_id, text = telegram.replies[0]
    assert chat_id == "555"
    assert "נרשמת" in text
    assert "20:00" in text and "שעון ישראל" in text  # the one fact they need
    assert "היי Shay" in text
    assert report.subscribed == 1


def test_starting_twice_does_not_repeat_the_welcome(subscribers):
    telegram = FakeTelegram([message(1, 555, "/start"), message(2, 555, "/start")])

    service(telegram, subscribers).sync()

    assert "נרשמת" in telegram.replies[0][1]
    assert "כבר רשומים" in telegram.replies[1][1]


def test_stop_unsubscribes_and_confirms(subscribers):
    subscribers.subscribe("555")
    telegram = FakeTelegram([message(1, 555, "/stop")])

    report = service(telegram, subscribers).sync()

    assert not subscribers.is_subscribed("555")
    assert "לא תקבלו יותר" in telegram.replies[0][1]
    assert report.unsubscribed == 1


def test_stopping_when_not_subscribed_explains_how_to_join(subscribers):
    telegram = FakeTelegram([message(1, 555, "/stop")])

    service(telegram, subscribers).sync()

    assert "/start" in telegram.replies[0][1]


def test_returning_subscriber_gets_a_welcome_back(subscribers):
    subscribers.subscribe("555")
    subscribers.unsubscribe("555")
    telegram = FakeTelegram([message(1, 555, "/start")])

    service(telegram, subscribers).sync()

    assert "שמחים שחזרתם" in telegram.replies[0][1]


def test_status_reports_the_subscription_and_the_time(subscribers):
    subscribers.subscribe("555")
    telegram = FakeTelegram([message(1, 555, "/status")])

    service(telegram, subscribers).sync()

    assert "המנוי פעיל" in telegram.replies[0][1]
    assert "20:00" in telegram.replies[0][1]


def test_a_command_addressed_to_the_bot_still_works(subscribers):
    # Telegram appends @botname to commands sent in groups.
    telegram = FakeTelegram([message(1, 555, "/start@shay_music_daily_bot")])

    service(telegram, subscribers).sync()

    assert subscribers.is_subscribed("555")


def test_anything_else_gets_the_help_text(subscribers):
    telegram = FakeTelegram([message(1, 555, "שלום")])

    service(telegram, subscribers).sync()

    assert "/start" in telegram.replies[0][1]
    assert not subscribers.is_subscribed("555")


def test_messages_from_other_bots_are_ignored(subscribers):
    telegram = FakeTelegram([message(1, 555, "/start", is_bot=True)])

    service(telegram, subscribers).sync()

    assert telegram.replies == []
    assert not subscribers.is_subscribed("555")


def test_handled_messages_are_never_replayed(subscribers):
    telegram = FakeTelegram([message(7, 555, "/start")])
    bot = service(telegram, subscribers)

    bot.sync()
    bot.sync()  # queue is empty now

    assert telegram.offsets == [None, 8]  # acknowledged past update 7
    assert len(telegram.replies) == 1


def test_a_failed_reply_does_not_stop_the_rest(subscribers):
    telegram = FakeTelegram([message(1, 111, "/start"), message(2, 222, "/start")])
    telegram.fail_for = {"111"}

    report = service(telegram, subscribers).sync()

    assert report.failed == 1
    assert [chat for chat, _ in telegram.replies] == ["222"]
    assert subscribers.is_subscribed("222")


# --------------------------------------------------------------------- #
# Catching a latecomer up on the song they missed
# --------------------------------------------------------------------- #


def test_a_newcomer_receives_the_song_already_published_today(
    subscribers, tmp_path, dossier
):
    telegram = FakeTelegram([message(1, 555, "/start")])
    songs = songs_with_today(tmp_path, dossier)

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    assert report.caught_up == 1
    # Welcome first, then the explanation, then the song itself.
    assert [chat for chat, _ in telegram.replies] == ["555", "555"]
    assert "נרשמת" in telegram.replies[0][1]
    assert "השיר של היום" in telegram.replies[1][1]
    chat_id, post = telegram.posts[0]
    assert chat_id == "555"
    assert "Torn" in post.text


def test_a_returning_subscriber_is_caught_up_too(subscribers, tmp_path, dossier):
    subscribers.subscribe("555")
    subscribers.unsubscribe("555")
    telegram = FakeTelegram([message(1, 555, "/start")])
    songs = songs_with_today(tmp_path, dossier)

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    assert report.caught_up == 1
    assert "שמחים שחזרתם" in telegram.replies[0][1]


def test_pressing_start_again_does_not_resend_the_song(subscribers, tmp_path, dossier):
    telegram = FakeTelegram([message(1, 555, "/start"), message(2, 555, "/start")])
    songs = songs_with_today(tmp_path, dossier)

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    # Only the first /start earns the catch-up; the second is already subscribed.
    assert report.caught_up == 1
    assert len(telegram.posts) == 1


def test_nothing_is_sent_when_today_has_no_song_yet(subscribers, tmp_path, dossier):
    telegram = FakeTelegram([message(1, 555, "/start")])
    songs = SongRepository(tmp_path / "songs.db")
    songs.initialize()

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    assert report.caught_up == 0
    assert telegram.posts == []
    assert len(telegram.replies) == 1  # the welcome, and nothing else


def test_yesterdays_song_is_not_resent(subscribers, tmp_path, dossier):
    telegram = FakeTelegram([message(1, 555, "/start")])
    songs = SongRepository(tmp_path / "songs.db")
    songs.initialize()
    songs.add(
        PublishedSong(
            song_id=make_song_id(dossier.artist, dossier.title),
            artist=dossier.artist,
            title=dossier.title,
            release_year=dossier.release_year,
            decade="90s",
            date_published=(
                datetime.now(ZoneInfo("Asia/Jerusalem")) - timedelta(days=1)
            ).date(),
            dossier_json=dossier.model_dump_json(),
        )
    )

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    assert report.caught_up == 0
    assert telegram.posts == []


def test_a_song_stored_without_a_dossier_is_skipped_quietly(
    subscribers, tmp_path, dossier
):
    telegram = FakeTelegram([message(1, 555, "/start")])
    songs = songs_with_today(tmp_path, dossier, keep_dossier=False)

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    # Rows written before the dossier was kept cannot be rebuilt — the
    # subscription must still succeed.
    assert report.caught_up == 0
    assert telegram.posts == []
    assert subscribers.is_subscribed("555")


def test_a_failed_catch_up_does_not_cost_the_subscription(
    subscribers, tmp_path, dossier
):
    telegram = FakeTelegram([message(1, 555, "/start")])
    telegram.fail_posts_for = {"555"}
    songs = songs_with_today(tmp_path, dossier)

    report = service(telegram, subscribers, catch_up_for(telegram, songs)).sync()

    # The bonus song is best-effort; the welcome and the subscription stand.
    assert subscribers.is_subscribed("555")
    assert report.caught_up == 0
    assert report.failed == 0
    assert "נרשמת" in telegram.replies[0][1]
