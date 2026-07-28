"""Claude API access: song selection and grounded research.

Two stages, both returning structured JSON:

1. :meth:`ClaudeMusicAgent.select_song` — no tools, pure editorial judgement
   under the constraints computed by :mod:`music_agent.music.selector`.
2. :meth:`ClaudeMusicAgent.research_song` — the server-side web search tool, so
   facts and links come from real sources instead of the model's memory.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

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
        client: Optional[anthropic.Anthropic] = None,
    ) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._effort = effort
        self._use_fallbacks = model in _FALLBACK_MODELS

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
            "model": self._model,
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
        """Send the request, preferring the server-side refusal fallback path."""
        if self._use_fallbacks:
            try:
                return self._client.beta.messages.create(
                    **request, betas=[_FALLBACK_BETA], fallbacks="default"
                )
            except (anthropic.BadRequestError, TypeError) as exc:
                logger.warning(
                    "Server-side fallbacks unavailable (%s); continuing without them.", exc
                )
                self._use_fallbacks = False
        return self._client.messages.create(**request)


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
    raise AgentError(f"No JSON object in the response (stop_reason={response.stop_reason}, "
                     f"errors={errors or 'no text blocks'}).")


def _validate(model: type[BaseModel], payload: dict[str, Any]) -> Any:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise AgentError(f"{model.__name__} did not match the expected shape: {exc}") from exc
