"""POST tests for the interpretation dashboard (save / save-and-test)."""

import pytest
from django.contrib.messages import get_messages
from django.test import override_settings

from interpretation.settings import (
    get_auth_token,
    get_base_url,
    is_interpretation_enabled,
)
from interpretation.susi import SusiResult

pytestmark = pytest.mark.django_db


@override_settings(SITE_URL="https://testserver")
def test_save_persists_connection(
    organizer_client, event, dashboard_url, connection_payload
):
    response = organizer_client.post(dashboard_url, connection_payload)

    assert response.status_code == 302
    event.refresh_from_db()
    event.settings.flush()
    assert get_base_url(event) == "https://susi.example.com"
    assert get_auth_token(event) == "jwt-test-token"
    assert is_interpretation_enabled(event) is True

    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("saved" in message.lower() for message in messages)


@override_settings(SITE_URL="https://testserver")
def test_save_and_test_calls_verify_with_saved_token(
    monkeypatch, organizer_client, event, dashboard_url, connection_payload
):
    calls = []

    class FakeSusiClient:
        def __init__(self, base_url, auth_token="", timeout=10):
            calls.append((base_url, auth_token))

        def verify(self):
            return SusiResult(
                ok=True,
                status_code=200,
                data={"authenticated": True},
                message="Connected and authenticated.",
            )

    monkeypatch.setattr("interpretation.views.SusiClient", FakeSusiClient)

    payload = {**connection_payload, "test": "1"}
    response = organizer_client.post(dashboard_url, payload)

    assert response.status_code == 302
    assert calls == [("https://susi.example.com", "jwt-test-token")]

    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("connection successful" in message.lower() for message in messages)


@override_settings(SITE_URL="https://testserver")
def test_save_and_test_warns_when_verify_rejects_token(
    monkeypatch, organizer_client, event, dashboard_url, connection_payload
):
    class FakeSusiClient:
        def __init__(self, base_url, auth_token="", timeout=10):
            self.base_url = base_url
            self.auth_token = auth_token

        def verify(self):
            return SusiResult(
                ok=False,
                status_code=200,
                data={"authenticated": False},
                message="Server reachable but token is invalid or expired.",
            )

    monkeypatch.setattr("interpretation.views.SusiClient", FakeSusiClient)

    payload = {**connection_payload, "test": "1"}
    response = organizer_client.post(dashboard_url, payload)

    assert response.status_code == 302
    event.refresh_from_db()
    event.settings.flush()
    assert get_auth_token(event) == "jwt-test-token"

    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("connection issue" in message.lower() for message in messages)
    assert any("invalid" in message.lower() for message in messages)


@override_settings(SITE_URL="https://testserver")
def test_save_and_test_without_url_shows_error(
    monkeypatch, organizer_client, event, dashboard_url
):
    calls = []

    class FakeSusiClient:
        def __init__(self, *args, **kwargs):
            calls.append(True)

    monkeypatch.setattr("interpretation.views.SusiClient", FakeSusiClient)

    response = organizer_client.post(dashboard_url, {"test": "1"})

    assert response.status_code == 302
    assert calls == []
    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("url" in message.lower() for message in messages)
