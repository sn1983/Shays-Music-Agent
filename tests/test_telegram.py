"""Telegram error reporting and the chat-id / bot-id confusion."""

from __future__ import annotations

import httpx
import pytest

from music_agent.config import ConfigError, load_settings
from music_agent.music.formatter import PostFormatter
from music_agent.telegram.client import TelegramClient, TelegramError


def client_returning(payload: dict, status: int = 200) -> TelegramClient:
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json=payload))
    return TelegramClient("111:AAA", "222", client=httpx.Client(transport=transport))


def test_sending_to_a_bot_explains_the_chat_id_mistake(dossier):
    telegram = client_returning(
        {
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: the bot can't send messages to the bot",
        }
    )

    with pytest.raises(TelegramError) as error:
        telegram.send_post(PostFormatter("HTML").format(dossier))

    assert "TELEGRAM_CHAT_ID" in str(error.value)
    assert "docs/TELEGRAM_SETUP.md" in str(error.value)


def test_a_missing_chat_is_explained():
    telegram = client_returning(
        {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
    )

    with pytest.raises(TelegramError, match="/start"):
        telegram.send_text("hello")


def test_an_unknown_error_is_still_reported_verbatim():
    telegram = client_returning(
        {"ok": False, "error_code": 400, "description": "Bad Request: message is too long"}
    )

    with pytest.raises(TelegramError, match="message is too long"):
        telegram.send_text("hello")


def test_the_bot_id_cannot_be_used_as_the_chat_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "8154392017:AAH9x7Kq")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8154392017")

    with pytest.raises(ConfigError, match="bot's own id"):
        load_settings(require_secrets=False)


def test_a_real_chat_id_passes_validation(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "8154392017:AAH9x7Kq")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "512345678")

    assert load_settings(require_secrets=False).telegram_chat_id == "512345678"


# --------------------------------------------------------------------- #
# The profile a newcomer sees before anyone replies to them
# --------------------------------------------------------------------- #


def test_the_profile_texts_fit_telegram_limits():
    from music_agent.telegram import messages as texts

    # Telegram rejects anything longer, and the failure only shows at setup time.
    assert len(texts.BOT_SHORT_DESCRIPTION) <= 120
    assert len(texts.bot_description("20:00", "Asia/Jerusalem")) <= 512
    for name, description in texts.BOT_COMMANDS:
        assert name.islower() and name.isalnum() and 1 <= len(name) <= 32
        assert len(description) <= 256


def test_the_pre_start_description_states_the_time_and_the_wait():
    from music_agent.telegram import messages as texts

    description = texts.bot_description("20:00", "Asia/Jerusalem")

    assert "20:00" in description
    assert "START" in description
    # A newcomer must know the confirmation is not instant.
    assert "כמה דקות" in description


def test_setup_publishes_commands_and_descriptions():
    calls: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        calls.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": True})

    from music_agent.telegram import messages as texts

    telegram = TelegramClient(
        "111:AAA", "222", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    telegram.set_my_commands(texts.BOT_COMMANDS)
    telegram.set_my_short_description(texts.BOT_SHORT_DESCRIPTION)
    telegram.set_my_description(texts.bot_description("20:00", "Asia/Jerusalem"))

    methods = [method for method, _ in calls]
    assert methods == ["setMyCommands", "setMyShortDescription", "setMyDescription"]
    assert calls[0][1]["commands"][0] == {"command": "start", "description": "הרשמה לשיר היומי"}
