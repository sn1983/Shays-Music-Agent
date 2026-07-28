"""Facebook Graph API client — publish, publish with image, and schedule.

Posting happens on a Facebook **Page**, using a long-lived Page access token.
Personal profiles cannot be posted to via the API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from music_agent.music.formatter import FacebookPost

logger = logging.getLogger(__name__)

API_ROOT = "https://graph.facebook.com"
DEFAULT_API_VERSION = "v21.0"

#: Graph API rejects a scheduled time closer than 10 minutes or further than
#: 6 months away, so callers get a clear error before the request goes out.
MIN_SCHEDULE_SECONDS = 10 * 60
MAX_SCHEDULE_SECONDS = 180 * 24 * 60 * 60


class FacebookError(RuntimeError):
    """Raised when the Graph API rejects a request."""


@dataclass(frozen=True)
class PublishedPost:
    """Identifiers Facebook returns for a published or scheduled post."""

    post_id: str
    scheduled: bool = False


class FacebookClient:
    """The handful of Graph API calls the agent needs."""

    def __init__(
        self,
        page_id: str,
        access_token: str,
        *,
        api_version: str = DEFAULT_API_VERSION,
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._page_id = page_id
        self._token = access_token
        self._base = f"{API_ROOT}/{api_version}"
        self._client = client or httpx.Client(timeout=timeout)

    def get_page(self) -> dict[str, Any]:
        """Verify the token and return the page's name/id."""
        return self._request(
            "GET", f"/{self._page_id}", {"fields": "id,name,fan_count"}
        )

    def publish(
        self, post: FacebookPost, *, publish_at: Optional[datetime] = None
    ) -> PublishedPost:
        """Publish now, or schedule for `publish_at`.

        A post with a verified album cover is published as a photo so the image
        is part of the post itself rather than a link preview.
        """
        params: dict[str, Any] = {}
        if publish_at is not None:
            params.update(
                published="false", scheduled_publish_time=self._timestamp(publish_at)
            )

        scheduled = publish_at is not None
        if post.photo_url:
            try:
                return self._publish_photo(post, params, scheduled=scheduled)
            except FacebookError as exc:
                logger.warning(
                    "Publishing with the album cover failed (%s); posting text only.", exc
                )

        result = self._request(
            "POST", f"/{self._page_id}/feed", {"message": post.message, **params}
        )
        return PublishedPost(post_id=str(result["id"]), scheduled=scheduled)

    # ------------------------------------------------------------------ #

    def _publish_photo(
        self, post: FacebookPost, params: dict[str, Any], *, scheduled: bool
    ) -> PublishedPost:
        result = self._request(
            "POST",
            f"/{self._page_id}/photos",
            {"url": post.photo_url, "caption": post.message, **params},
        )
        # The photos edge returns both the photo id and the feed post id.
        post_id = result.get("post_id") or result["id"]
        return PublishedPost(post_id=str(post_id), scheduled=scheduled)

    @staticmethod
    def _timestamp(publish_at: datetime) -> int:
        moment = (
            publish_at
            if publish_at.tzinfo is not None
            else publish_at.replace(tzinfo=timezone.utc)
        )
        delta = (moment - datetime.now(timezone.utc)).total_seconds()
        if delta < MIN_SCHEDULE_SECONDS:
            raise FacebookError(
                "Facebook requires a scheduled post to be at least 10 minutes away."
            )
        if delta > MAX_SCHEDULE_SECONDS:
            raise FacebookError(
                "Facebook requires a scheduled post to be at most 6 months away."
            )
        return int(moment.timestamp())

    def _request(self, method: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}{path}"
        payload = {**params, "access_token": self._token}
        try:
            if method == "GET":
                response = self._client.get(url, params=payload)
            else:
                response = self._client.post(url, data=payload)
        except httpx.HTTPError as exc:
            raise FacebookError(f"{method} {path} failed: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise FacebookError(f"{method} {path} returned a non-JSON response.") from exc

        if "error" in body:
            error = body["error"]
            raise FacebookError(
                f"{error.get('message', 'unknown error')} "
                f"(type={error.get('type')}, code={error.get('code')})"
            )
        if not response.is_success:
            raise FacebookError(f"{method} {path} failed with HTTP {response.status_code}.")
        return body
