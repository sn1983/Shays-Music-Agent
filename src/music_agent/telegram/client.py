"""Telegram Bot API client — just the calls this agent needs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from music_agent.music.formatter import TelegramPost

logger = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"


class TelegramError(RuntimeError):
    """Raised when the Bot API rejects a request."""


@dataclass(frozen=True)
class SentMessage:
    """Identifiers returned by Telegram for a delivered post."""

    message_id: int
    chat_id: int | str


class TelegramClient:
    """Sends the daily post: photo + caption, or plain text, plus link buttons."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        parse_mode: str = "HTML",
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._parse_mode = parse_mode
        self._client = client or httpx.Client(timeout=timeout)

    def get_me(self) -> dict[str, Any]:
        """Verify the bot token; used by the `test-telegram` command."""
        return self._request("getMe", {})

    def send_post(self, post: TelegramPost) -> SentMessage:
        """Deliver a post, falling back to text if the photo cannot be sent."""
        keyboard = _keyboard(post.buttons)

        if post.photo_url and post.fits_in_caption:
            try:
                result = self._request(
                    "sendPhoto",
                    self._payload(
                        photo=post.photo_url,
                        caption=post.text,
                        reply_markup=keyboard,
                    ),
                )
                return _to_sent_message(result)
            except TelegramError as exc:
                logger.warning("sendPhoto failed (%s); falling back to sendMessage.", exc)

        result = self._request(
            "sendMessage",
            self._payload(
                text=post.text,
                reply_markup=keyboard,
                link_preview_options={"is_disabled": not post.photo_url},
            ),
        )
        return _to_sent_message(result)

    def send_text(self, text: str) -> SentMessage:
        """Send a plain notification (errors, health checks)."""
        return _to_sent_message(self._request("sendMessage", self._payload(text=text)))

    # ------------------------------------------------------------------ #

    def _payload(self, **fields: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": self._chat_id, "parse_mode": self._parse_mode}
        payload.update({key: value for key, value in fields.items() if value is not None})
        return payload

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{API_ROOT}/bot{self._token}/{method}"
        try:
            response = self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise TelegramError(f"{method} failed: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise TelegramError(f"{method} returned a non-JSON response.") from exc

        if not body.get("ok"):
            raise TelegramError(
                f"{method} failed: {body.get('description', 'unknown error')} "
                f"(error_code={body.get('error_code')})"
            )
        return body["result"]


def _keyboard(buttons: tuple[tuple[str, str], ...]) -> dict[str, Any] | None:
    """Two buttons per row, so labels stay readable on a phone."""
    if not buttons:
        return None
    rows = [
        [{"text": label, "url": url} for label, url in buttons[index : index + 2]]
        for index in range(0, len(buttons), 2)
    ]
    return {"inline_keyboard": rows}


def _to_sent_message(result: dict[str, Any]) -> SentMessage:
    return SentMessage(
        message_id=int(result["message_id"]),
        chat_id=result.get("chat", {}).get("id", ""),
    )
