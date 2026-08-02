"""Handling incoming Telegram messages: /start, /stop, /status, /help.

Two ways to run this, both on the same handler:

* :meth:`SubscriptionService.sync` — one drain of `getUpdates`. Cheap enough to
  run from a scheduled job, which is how the GitHub Actions deployment works.
* :meth:`SubscriptionService.run_forever` — long polling, for an always-on
  machine, where a new subscriber is greeted within a second.

The update offset is stored in the database, so both modes can be used
interchangeably without replaying or dropping a message.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from music_agent.database.subscribers import SubscriberRepository, SubscriptionChange
from music_agent.telegram import messages as texts
from music_agent.telegram.catch_up import DailyCatchUp
from music_agent.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 25


@dataclass
class SyncReport:
    """What one drain of the update queue did."""

    processed: int = 0
    subscribed: int = 0
    unsubscribed: int = 0
    failed: int = 0
    caught_up: int = 0
    new_names: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"עודכנו {self.processed} הודעות | "
            f"נרשמו: {self.subscribed} | הוסרו: {self.unsubscribed} | "
            f"השלמות: {self.caught_up} | שגיאות: {self.failed}"
        )


class SubscriptionService:
    """Turns incoming messages into subscription changes and replies."""

    def __init__(
        self,
        telegram: TelegramClient,
        subscribers: SubscriberRepository,
        *,
        post_time: str,
        timezone: str,
        catch_up: Optional[DailyCatchUp] = None,
    ) -> None:
        self._telegram = telegram
        self._subscribers = subscribers
        self._post_time = post_time
        self._timezone = timezone
        self._catch_up = catch_up

    def sync(self) -> SyncReport:
        """Handle everything waiting in the queue, then return."""
        report = SyncReport()
        updates = self._telegram.get_updates(offset=self._subscribers.update_offset())
        for update in updates:
            self._handle(update, report)
        return report

    def run_forever(self, *, poll_timeout: int = POLL_TIMEOUT_SECONDS) -> None:
        """Long-poll until interrupted. Replies land within a second."""
        logger.info("Bot is listening. Press Ctrl+C to stop.")
        while True:
            try:
                updates = self._telegram.get_updates(
                    offset=self._subscribers.update_offset(), timeout=poll_timeout
                )
            except TelegramError as exc:
                # A blip in connectivity should not end the session; the next
                # poll picks up from the same offset.
                logger.warning("Polling failed (%s); retrying.", exc)
                continue

            report = SyncReport()
            for update in updates:
                self._handle(update, report)
            if report.processed:
                logger.info(report.summary())

    # ------------------------------------------------------------------ #

    def _handle(self, update: dict[str, Any], report: SyncReport) -> None:
        # Acknowledge first: a message that crashes the handler must not be
        # replayed forever on every subsequent poll.
        update_id = update.get("update_id")
        if update_id is not None:
            self._subscribers.set_update_offset(int(update_id) + 1)

        message = update.get("message")
        if not isinstance(message, dict):
            return

        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", "")).strip()
        if not chat_id:
            return

        report.processed += 1
        sender = message.get("from") or {}
        if sender.get("is_bot"):
            return

        command = _command_of(message.get("text", ""))
        try:
            self._dispatch(command, chat_id, chat, sender, report)
        except TelegramError as exc:
            report.failed += 1
            logger.warning("Could not reply to %s: %s", chat_id, exc)

    def _dispatch(
        self,
        command: str,
        chat_id: str,
        chat: dict[str, Any],
        sender: dict[str, Any],
        report: SyncReport,
    ) -> None:
        first_name = sender.get("first_name") or chat.get("first_name")
        username = sender.get("username") or chat.get("username")

        if command in {"/start", "/subscribe"}:
            change = self._subscribers.subscribe(
                chat_id, first_name=first_name, username=username
            )
            self._telegram.send_text(self._greeting(change, first_name), chat_id)
            if change is SubscriptionChange.NEW:
                report.subscribed += 1
                report.new_names.append(username and f"@{username}" or first_name or chat_id)
            elif change is SubscriptionChange.RESUBSCRIBED:
                report.subscribed += 1
            logger.info("Subscription %s for %s.", change.value, chat_id)
            # Someone joining after the evening post would otherwise wait a full
            # day for their first song. Pressing /start while already subscribed
            # is deliberately excluded, so the song cannot be requested twice.
            if self._catch_up is not None and change is not SubscriptionChange.ALREADY_SUBSCRIBED:
                report.caught_up += self._catch_up.send_to(chat_id)
            return

        if command in {"/stop", "/unsubscribe"}:
            removed = self._subscribers.unsubscribe(chat_id)
            self._telegram.send_text(
                texts.goodbye() if removed else texts.not_subscribed(), chat_id
            )
            if removed:
                report.unsubscribed += 1
                logger.info("%s unsubscribed.", chat_id)
            return

        if command == "/status":
            self._telegram.send_text(
                texts.status(
                    self._subscribers.is_subscribed(chat_id), self._post_time, self._timezone
                ),
                chat_id,
            )
            return

        # Anything else — /help, an unknown command, or plain chatter — gets the
        # help text, so a first-time visitor always learns how to subscribe.
        self._telegram.send_text(texts.help_text(self._post_time, self._timezone), chat_id)

    def _greeting(self, change: SubscriptionChange, first_name: Optional[str]) -> str:
        if change is SubscriptionChange.NEW:
            return texts.welcome(self._post_time, self._timezone, first_name=first_name)
        if change is SubscriptionChange.RESUBSCRIBED:
            return texts.welcome_back(self._post_time, self._timezone)
        return texts.already_subscribed(self._post_time, self._timezone)


def _command_of(text: str) -> str:
    """First word, lowercased, with any `@botname` suffix removed."""
    first = (text or "").strip().split(maxsplit=1)
    if not first:
        return ""
    return first[0].split("@", 1)[0].lower()
