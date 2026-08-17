"""Tests for the dependency-free DCSServerBot API wrapper."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

# Import the dependency-free API wrapper without executing the Home Assistant
# integration package. This keeps the API unit tests runnable on development
# machines that do not have a full Home Assistant runtime installed.
PACKAGE_NAME = "custom_components.dcs_server_bot"
if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [
        str(Path(__file__).parents[1] / "custom_components" / "dcs_server_bot")
    ]
    sys.modules[PACKAGE_NAME] = package

api = importlib.import_module(f"{PACKAGE_NAME}.api")
DCSServerBotAuthenticationError = api.DCSServerBotAuthenticationError
DCSServerBotClient = api.DCSServerBotClient
DCSServerBotResponseError = api.DCSServerBotResponseError

class FakeResponse:
    def __init__(self, status: int, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.request_data = None

    def request(self, method, url, **kwargs):
        self.request_data = (method, url, kwargs)
        return self.response


@pytest.mark.asyncio
async def test_servers_are_parsed_and_password_is_removed():
    session = FakeSession(
        FakeResponse(
            200,
            [
                {
                    "name": "Training",
                    "status": "running",
                    "password": "must-not-leak",
                    "players": [{"nick": "Pilot"}],
                    "extensions": [{"name": "SRS"}],
                }
            ],
        )
    )
    client = DCSServerBotClient(session, "http://127.0.0.1:9876/", "secret")

    servers = await client.async_get_servers()

    assert servers[0]["name"] == "Training"
    assert "password" not in servers[0]
    assert session.request_data[1] == "http://127.0.0.1:9876/servers"
    assert session.request_data[2]["headers"]["X-API-Key"] == "secret"


@pytest.mark.asyncio
async def test_authentication_error():
    client = DCSServerBotClient(
        FakeSession(FakeResponse(403, {"detail": "Forbidden"})),
        "http://127.0.0.1:9876",
        "wrong",
    )

    with pytest.raises(DCSServerBotAuthenticationError):
        await client.async_get_servers()


@pytest.mark.asyncio
async def test_invalid_servers_payload():
    client = DCSServerBotClient(
        FakeSession(FakeResponse(200, {"servers": []})),
        "http://127.0.0.1:9876",
        "secret",
    )

    with pytest.raises(DCSServerBotResponseError):
        await client.async_get_servers()


@pytest.mark.asyncio
async def test_moderation_health_uses_companion_url():
    session = FakeSession(
        FakeResponse(200, {"status": "ok", "service": "dcs-ha-moderation-bridge"})
    )
    client = DCSServerBotClient(
        session,
        "http://127.0.0.1:9876",
        "secret",
        moderation_url="http://127.0.0.1:9877/",
    )

    assert await client.async_check_moderation() is True
    assert session.request_data[1] == "http://127.0.0.1:9877/health"


@pytest.mark.asyncio
async def test_ban_payload_is_sent_to_companion_bridge():
    session = FakeSession(FakeResponse(200, {"status": "ok", "action": "ban"}))
    client = DCSServerBotClient(
        session,
        "http://127.0.0.1:9876",
        "secret",
        moderation_url="http://127.0.0.1:9877",
    )

    await client.async_moderate(
        "ban",
        "Pilot",
        server_name="Training",
        reason="Test",
        days=7,
    )

    method, url, kwargs = session.request_data
    assert method == "POST"
    assert url == "http://127.0.0.1:9877/ban"
    assert kwargs["json"] == {
        "player_name": "Pilot",
        "reason": "Test",
        "server_name": "Training",
        "days": 7,
    }
