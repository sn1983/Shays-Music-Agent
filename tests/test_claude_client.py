"""Resilience of the Claude calls: retries, model fallback, response parsing.

No network. A fake stands in for the SDK client, so the retry policy is
exercised deterministically and `sleep` is replaced with a recorder.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from music_agent.ai.claude_client import RETRY_DELAYS, AgentError, ClaudeMusicAgent
from music_agent.models import SongSelection
from music_agent.music.selector import build_plan


def overloaded() -> anthropic.OverloadedError:
    """The 529 that took down the first scheduled run."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(529, request=request, json={"error": {"message": "Overloaded"}})
    return anthropic.OverloadedError("Overloaded", response=response, body=None)


def selection_payload(**overrides) -> str:
    payload = {
        "artist": "Natalie Imbruglia",
        "title": "Torn",
        "release_year": 1997,
        "genre": "Pop Rock",
        "category": "big-hit",
        "reason": "בדיקה",
    }
    payload.update(overrides)
    return json.dumps(payload)


def message(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=None,
    )


class FakeStream:
    def __init__(self, result) -> None:
        self._result = result

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def get_final_message(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class FakeMessages:
    """Replays a queued list of results (or exceptions), one per call."""

    def __init__(self, results: list) -> None:
        self._results = list(results)
        self.models: list[str] = []

    def stream(self, **params):
        self.models.append(params["model"])
        result = self._results.pop(0) if self._results else self._results
        if isinstance(result, Exception):
            raise result
        return FakeStream(result)


class FakeClient:
    def __init__(self, results: list) -> None:
        self.messages = FakeMessages(results)
        # The agent only uses the beta path for server-side refusal fallbacks;
        # routing it to the same fake keeps the call sequence in one place.
        self.beta = SimpleNamespace(messages=self.messages)


def make_agent(results: list, **overrides) -> tuple[ClaudeMusicAgent, list[int]]:
    slept: list[int] = []
    agent = ClaudeMusicAgent(
        "test-key",
        client=FakeClient(results),
        sleep=slept.append,
        **overrides,
    )
    return agent, slept


@pytest.fixture
def plan():
    from collections import Counter

    return build_plan([], Counter())


# --------------------------------------------------------------------- #


def test_a_successful_call_returns_the_parsed_selection(plan):
    agent, slept = make_agent([message(selection_payload())])

    result = agent.select_song(plan)

    assert isinstance(result, SongSelection)
    assert (result.artist, result.release_year) == ("Natalie Imbruglia", 1997)
    assert slept == []


def test_an_overloaded_api_is_retried_rather_than_failing(plan):
    agent, slept = make_agent([overloaded(), overloaded(), message(selection_payload())])

    assert agent.select_song(plan).title == "Torn"
    # Waited between attempts instead of giving up in seconds, as the run did.
    assert slept == [RETRY_DELAYS[0], RETRY_DELAYS[1]]


def test_a_persistently_overloaded_model_falls_back_to_another(plan):
    attempts = len(RETRY_DELAYS) + 1
    agent, _ = make_agent(
        [overloaded()] * attempts + [message(selection_payload())],
        model="claude-opus-5",
        fallback_model="claude-sonnet-5",
    )

    assert agent.select_song(plan).title == "Torn"
    assert agent._client.messages.models[-1] == "claude-sonnet-5"


def test_the_fallback_model_is_skipped_when_disabled(plan):
    attempts = len(RETRY_DELAYS) + 1
    agent, _ = make_agent([overloaded()] * attempts, fallback_model=None)

    with pytest.raises(AgentError, match="stayed unavailable"):
        agent.select_song(plan)

    assert set(agent._client.messages.models) == {"claude-opus-5"}


def test_every_attempt_failing_raises_a_readable_error(plan):
    attempts = (len(RETRY_DELAYS) + 1) * 2  # primary + fallback
    agent, _ = make_agent([overloaded()] * attempts)

    with pytest.raises(AgentError, match="stayed unavailable"):
        agent.select_song(plan)


def test_a_timeout_is_treated_as_transient(plan):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    agent, slept = make_agent(
        [anthropic.APITimeoutError(request=request), message(selection_payload())]
    )

    assert agent.select_song(plan).title == "Torn"
    assert slept == [RETRY_DELAYS[0]]


def test_a_bad_api_key_is_not_retried(plan):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request, json={"error": {"message": "bad key"}})
    agent, slept = make_agent(
        [anthropic.AuthenticationError("invalid x-api-key", response=response, body=None)]
    )

    with pytest.raises(anthropic.AuthenticationError):
        agent.select_song(plan)

    assert slept == []  # retrying a rejected key would only waste time


def test_a_paused_tool_loop_is_resumed(plan):
    agent, _ = make_agent(
        [message("", stop_reason="pause_turn"), message(selection_payload())]
    )

    assert agent.select_song(plan).title == "Torn"
    assert len(agent._client.messages.models) == 2


def test_a_refusal_is_reported_clearly(plan):
    refusal = message("", stop_reason="refusal")
    refusal.stop_details = SimpleNamespace(category="cyber")
    agent, _ = make_agent([refusal])

    with pytest.raises(AgentError, match="declined"):
        agent.select_song(plan)


def test_json_wrapped_in_a_code_fence_is_still_parsed(plan):
    agent, _ = make_agent([message(f"```json\n{selection_payload()}\n```")])

    assert agent.select_song(plan).artist == "Natalie Imbruglia"


def test_a_malformed_payload_is_reported_not_swallowed(plan):
    agent, _ = make_agent([message(selection_payload(release_year="not a year"))])

    with pytest.raises(AgentError, match="SongSelection"):
        agent.select_song(plan)
