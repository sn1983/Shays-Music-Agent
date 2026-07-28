from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
import pytest

from music_agent.facebook.client import FacebookClient, FacebookError
from music_agent.models import SongDossier
from music_agent.music.formatter import FacebookPostFormatter


def make_client(handler) -> FacebookClient:
    transport = httpx.MockTransport(handler)
    return FacebookClient("page-1", "token-1", client=httpx.Client(transport=transport))


def body_of(request: httpx.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


# --------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------- #


def test_the_facebook_post_carries_the_links_as_text(dossier: SongDossier):
    post = FacebookPostFormatter().format(dossier)

    assert "🎧 Spotify: https://open.spotify.com/track/example" in post.message
    assert "🌍 Wikipedia: https://en.wikipedia.org/wiki/Torn" in post.message
    assert post.photo_url == "https://example.com/cover.jpg"


def test_the_facebook_post_is_plain_text(dossier: SongDossier):
    post = FacebookPostFormatter().format(dossier.model_copy(update={"album": "A & B <Live>"}))

    assert "<b>" not in post.message
    assert "A & B <Live>" in post.message  # no HTML escaping on Facebook
    assert "שיר היום" in post.message
    assert "מה דעתכם על השיר?" in post.message


# --------------------------------------------------------------------- #
# Publishing
# --------------------------------------------------------------------- #


def test_a_post_with_a_cover_goes_to_the_photos_edge(dossier: SongDossier):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "photo_1", "post_id": "page_1_post_9"})

    published = make_client(handler).publish(FacebookPostFormatter().format(dossier))

    assert seen[0].url.path.endswith("/page-1/photos")
    assert body_of(seen[0])["url"] == "https://example.com/cover.jpg"
    # The feed post id is what identifies the post, not the photo id.
    assert published.post_id == "page_1_post_9"
    assert not published.scheduled


def test_a_post_without_a_cover_goes_to_the_feed(dossier: SongDossier):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "page_1_post_5"})

    post = FacebookPostFormatter().format(dossier.model_copy(update={"album_cover_url": None}))
    published = make_client(handler).publish(post)

    assert seen[0].url.path.endswith("/page-1/feed")
    assert published.post_id == "page_1_post_5"


def test_a_failed_photo_upload_falls_back_to_a_text_post(dossier: SongDossier):
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/photos"):
            return httpx.Response(
                400, json={"error": {"message": "Image not reachable", "code": 324}}
            )
        return httpx.Response(200, json={"id": "page_1_post_7"})

    published = make_client(handler).publish(FacebookPostFormatter().format(dossier))

    assert [path.split("/")[-1] for path in paths] == ["photos", "feed"]
    assert published.post_id == "page_1_post_7"


def test_scheduling_sends_an_unpublished_post_with_a_timestamp(dossier: SongDossier):
    seen: list[httpx.Request] = []
    when = datetime.now(timezone.utc) + timedelta(hours=3)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "photo_1", "post_id": "page_1_post_3"})

    published = make_client(handler).publish(
        FacebookPostFormatter().format(dossier), publish_at=when
    )
    payload = body_of(seen[0])

    assert payload["published"] == "false"
    assert int(payload["scheduled_publish_time"]) == int(when.timestamp())
    assert published.scheduled


def test_a_schedule_too_close_to_now_is_rejected_before_the_request(dossier: SongDossier):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be sent")

    with pytest.raises(FacebookError, match="at least 10 minutes"):
        make_client(handler).publish(
            FacebookPostFormatter().format(dossier),
            publish_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        )


def test_a_schedule_too_far_out_is_rejected(dossier: SongDossier):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be sent")

    with pytest.raises(FacebookError, match="at most 6 months"):
        make_client(handler).publish(
            FacebookPostFormatter().format(dossier),
            publish_at=datetime.now(timezone.utc) + timedelta(days=400),
        )


def test_a_graph_api_error_is_reported_with_its_message(dossier: SongDossier):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Invalid OAuth access token",
                    "type": "OAuthException",
                    "code": 190,
                }
            },
        )

    post = FacebookPostFormatter().format(dossier.model_copy(update={"album_cover_url": None}))
    with pytest.raises(FacebookError, match="Invalid OAuth access token"):
        make_client(handler).publish(post)


def test_get_page_verifies_the_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert "access_token=token-1" in str(request.url)
        return httpx.Response(200, json={"id": "page-1", "name": "Shay's Music", "fan_count": 12})

    assert make_client(handler).get_page()["name"] == "Shay's Music"
