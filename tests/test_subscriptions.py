"""Subscriptions: the list itself, and the /start and /stop conversation."""

from __future__ import annotations

import pytest

from music_agent.database.subscribers import SubscriberRepository, SubscriptionChange
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
        self.offsets: list[int | None] = []
        self.fail_for: set[str] = set()

    def get_updates(self, *, offset=None, timeout=0):
        self.offsets.append(offset)
        pending, self.updates = self.updates, []
        return pending

    def send_text(self, text: str, chat_id: str | None = None):
        if chat_id in self.fail_for:
            raise TelegramError("Forbidden: bot was blocked by the user")
        self.replies.append((chat_id, text))
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


def service(telegram, subscribers) -> SubscriptionService:
    return SubscriptionService(
        telegram, subscribers, post_time="20:00", timezone="Asia/Jerusalem"
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
