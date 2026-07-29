"""Claude API access: song selection and grounded research.

Two stages, both returning structured JSON:

1. :meth:`ClaudeMusicAgent.select_song` — no tools, pure editorial judgement
   under the constraints computed by :mod:`music_agent.music.selector`.
2. :meth:`ClaudeMusicAgent.research_song` — the server-side web search tool, so
   facts and links come from real sources instead of the model's memory.

Both calls are streamed. A research turn that runs many web searches can take
several minutes, and a non-streaming request that long trips the SDK's HTTP
read timeout; streaming keeps the connection alive and is the supported way to
make long agentic calls.

The API can also be transiently unavailable — a `529 Overloaded` at peak time
is normal and says nothing about the request. Because this agent runs once a
day, giving up after a few seconds would cost a whole day of publishing, so a
transient failure is retried with a long backoff and, if the primary model
stays unavailable, the same request is tried once on a fallback model.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Iterator, Optional

import anthropic
from pydantic import BaseModel, ValidationError

from music_agent.ai.prompts import (
    RESEARCH_SYSTEM_PROMPT,
    SELECTION_SYSTEM_PROMPT,
    build_research_prompt,
    build_selection_prompt,
)
from music_agent.models import SongDossier, SongSelection, json_schema_for
from music_agent.music.selector import SelectionPlan

logger = logging.getLogger(__name__)

# Models that ship with safety classifiers able to decline a request; for these
# we opt into server-side fallbacks so a false positive does not lose the run.
_FALLBACK_MODELS = frozenset({"claude-opus-5", "claude-fable-5", "claude-mythos-5"})
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 8,
}

_MAX_TOKENS = 16000
_MAX_PAUSE_RESUMES = 6

#: How long to wait between attempts when the API is overloaded or unreachable.
#: Overload usually clears within a minute or two, and a daily job can afford
#: the wait far more than it can afford to skip a day.
RETRY_DELAYS: tuple[int, ...] = (20, 60, 120)

#: Failures that are worth retrying: nothing about the request caused them.
_TRANSIENT_ERRORS = (
    anthropic.OverloadedError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
)

#: Per-request ceiling. Streaming keeps the socket busy, so this only guards
#: against a genuinely stuck connection.
REQUEST_TIMEOUT_SECONDS = 900.0

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AgentError(RuntimeError):
    """Raised when Claude could not produce a usable result."""


class ClaudeMusicAgent:
    """Thin, typed wrapper over the two Claude calls the pipeline needs."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-opus-5",
        effort: str = "high",
        fallback_model: Optional[str] = "claude-sonnet-5",
        client: Optional[anthropic.Anthropic] = None,
        sleep: Any = time.sleep,
    ) -> None:
        self._client = client or anthropic.Anthropic(
            api_key=api_key,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=3,
        )
        self._model = model
        self._effort = effort
        self._fallback_model = fallback_model if fallback_model != model else None
        self._use_fallbacks = model in _FALLBACK_MODELS
        self._sleep = sleep

    def select_song(self, plan: SelectionPlan) -> SongSelection:
        """Stage 1: choose today's song under the given constraints."""
        payload = self._structured_request(
            system=SELECTION_SYSTEM_PROMPT,
            user_prompt=build_selection_prompt(plan),
            schema_model=SongSelection,
        )
        return _validate(SongSelection, payload)

    def research_song(self, selection: SongSelection) -> SongDossier:
        """Stage 2: verify the song on the web and write the Hebrew post."""
        payload = self._structured_request(
            system=RESEARCH_SYSTEM_PROMPT,
            user_prompt=build_research_prompt(
                selection.artist, selection.title, selection.release_year
            ),
            schema_model=SongDossier,
            tools=[_WEB_SEARCH_TOOL],
        )
        return _validate(SongDossier, payload)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _structured_request(
        self,
        *,
        system: str,
        user_prompt: str,
        schema_model: type[BaseModel],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        request: dict[str, Any] = {
            "max_tokens": _MAX_TOKENS,
            "system": system,
            "output_config": {
                "effort": self._effort,
                "format": {
                    "type": "json_schema",
                    "schema": json_schema_for(schema_model),
                },
            },
        }
        if tools:
            request["tools"] = tools

        for attempt in range(_MAX_PAUSE_RESUMES):
            response = self._call(dict(request, messages=messages))

            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None)
                raise AgentError(f"Claude declined the request (category={category}).")

            if response.stop_reason == "pause_turn":
                # A long server-tool turn hit its iteration limit; echo the
                # assistant turn back and the server resumes where it stopped.
                logger.info("Server tool loop paused, resuming (round %d).", attempt + 1)
                messages = [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": response.content},
                ]
                continue

            if response.stop_reason == "max_tokens":
                raise AgentError("Claude hit max_tokens before finishing the JSON output.")

            return _extract_json(response)

        raise AgentError("Claude kept pausing the tool loop without producing a result.")

    def _call(self, request: dict[str, Any]) -> Any:
        """Send the request, retrying transient failures and then the fallback model."""
        last_error: Optional[Exception] = None

        for model in self._candidate_models():
            for attempt in range(len(RETRY_DELAYS) + 1):
                try:
                    return self._send(model, request)
                except _TRANSIENT_ERRORS as exc:
                    last_error = exc
                    if attempt < len(RETRY_DELAYS):
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(
                            "%s is unavailable (%s). Retrying in %ds (attempt %d/%d).",
                            model,
                            type(exc).__name__,
                            delay,
                            attempt + 1,
                            len(RETRY_DELAYS),
                        )
                        self._sleep(delay)
                    else:
                        logger.error("%s still unavailable after %d attempts.", model, attempt + 1)

        raise AgentError(
            f"The Claude API stayed unavailable across every attempt: {last_error}"
        ) from last_error

    def _candidate_models(self) -> Iterator[str]:
        yield self._model
        if self._fallback_model:
            logger.warning("Falling back to %s for this request.", self._fallback_model)
            yield self._fallback_model

    def _send(self, model: str, request: dict[str, Any]) -> Any:
        """One streamed request. Streaming avoids read timeouts on long turns."""
        payload = dict(request, model=model)

        if self._use_fallbacks and model in _FALLBACK_MODELS:
            try:
                with self._client.beta.messages.stream(
                    **payload, betas=[_FALLBACK_BETA], fallbacks="default"
                ) as stream:
                    return stream.get_final_message()
            except (anthropic.BadRequestError, TypeError) as exc:
                logger.warning(
                    "Server-side refusal fallbacks unavailable (%s); continuing without them.",
                    exc,
                )
                self._use_fallbacks = False

        with self._client.messages.stream(**payload) as stream:
            return stream.get_final_message()


def _extract_json(response: Any) -> dict[str, Any]:
    """Pull the structured payload out of the response's text blocks."""
    errors: list[str] = []
    for block in reversed(list(response.content)):
        if getattr(block, "type", None) != "text":
            continue
        text = _CODE_FENCE.sub("", block.text).strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if isinstance(payload, dict):
            return payload
    raise AgentError(
        f"No JSON object in the response (stop_reason={response.stop_reason}, "
        f"errors={errors or 'no text blocks'})."
    )


def _validate(model: type[BaseModel], payload: dict[str, Any]) -> Any:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise AgentError(f"{model.__name__} did not match the expected shape: {exc}") from exc
