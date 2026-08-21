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
    package.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "dcs_server_bot")]
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
    def __init__(self, response: FakeResponse | list[FakeResponse]):
        self.responses = response if isinstance(response, list) else [response]
        self.request_data = None
        self.requests = []

    def request(self, method, url, **kwargs):
        self.request_data = (method, url, kwargs)
        self.requests.append(self.request_data)
        return self.responses.pop(0)


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


@pytest.mark.asyncio
async def test_mission_restart_timeout_falls_back_to_server_restart():
    session = FakeSession(
        [
            FakeResponse(504, {"detail": "Timeout while restarting mission."}),
            FakeResponse(200, {"status": "success"}),
        ]
    )
    client = DCSServerBotClient(
        session,
        "http://127.0.0.1:9876",
        "secret",
    )

    result = await client.async_control("/instance/mission/restart", "Training")

    assert result["fallback"] == "server_restart"
    assert [request[1] for request in session.requests] == [
        "http://127.0.0.1:9876/instance/mission/restart",
        "http://127.0.0.1:9876/instance/restart",
    ]
    assert all(request[2]["timeout"].total == 600 for request in session.requests)


@pytest.mark.asyncio
async def test_other_mission_restart_errors_are_not_hidden():
    session = FakeSession(FakeResponse(409, {"detail": "Server is stopped."}))
    client = DCSServerBotClient(
        session,
        "http://127.0.0.1:9876",
        "secret",
    )

    with pytest.raises(DCSServerBotResponseError, match="Server is stopped"):
        await client.async_control("/instance/mission/restart", "Training")

    assert len(session.requests) == 1


@pytest.mark.asyncio
async def test_rankings_and_airbases_are_parsed():
    session = FakeSession(
        [
            FakeResponse(200, [{"nick": "Ace", "kills": 42}]),
            FakeResponse(200, {"airbases": [{"name": "Kutaisi"}]}),
            FakeResponse(
                200,
                {
                    "warehouse": {"aircraft": {"F-16C_50": 4}},
                    "unlimited": {"aircraft": False},
                },
            ),
        ]
    )
    client = DCSServerBotClient(session, "http://127.0.0.1:9876", "secret")

    assert (await client.async_get_top_kills())[0]["nick"] == "Ace"
    assert (await client.async_get_airbases("Training"))[0]["name"] == "Kutaisi"
    warehouse = await client.async_get_airbase_warehouse("Training", "Kutaisi")
    assert warehouse["warehouse"]["aircraft"]["F-16C_50"] == 4
    assert session.requests[1][2]["params"] == {"server_name": "Training"}
    assert session.requests[2][2]["timeout"].total == 75


@pytest.mark.asyncio
async def test_operations_snapshot_uses_companion_bridge():
    session = FakeSession(
        FakeResponse(
            200,
            {
                "status": "ok",
                "performance": {"Training": {"fps": 60, "memory_gib": 9.3}},
                "missions": [],
                "vip_players": ["Ace"],
            },
        )
    )
    client = DCSServerBotClient(
        session,
        "http://127.0.0.1:9876",
        "secret",
        moderation_url="http://127.0.0.1:9877",
    )

    snapshot = await client.async_get_operations_snapshot()

    assert snapshot["performance"]["Training"]["fps"] == 60
    assert snapshot["performance"]["Training"]["memory_gib"] == 9.3
    assert session.request_data[1] == "http://127.0.0.1:9877/operations/snapshot"


@pytest.mark.asyncio
async def test_greenieboard_uses_form_payload():
    session = FakeSession(
        FakeResponse(200, {"players": [{"nick": "Ace", "traps": [{"grade": "OK"}]}]})
    )
    client = DCSServerBotClient(session, "http://127.0.0.1:9876", "secret")

    payload = await client.async_get_greenieboard("Training")

    assert payload["players"][0]["nick"] == "Ace"
    assert session.request_data[0] == "POST"
    assert session.request_data[1] == "http://127.0.0.1:9876/greenieboard"
    assert session.request_data[2]["data"] == {"server_name": "Training"}


@pytest.mark.asyncio
async def test_live_mission_layers_are_parsed():
    session = FakeSession(
        [
            FakeResponse(200, {"bullseyes": [{"coalition": "blue", "lat": 1, "lng": 2}]}),
            FakeResponse(
                200,
                {
                    "drawings": {
                        "Author": [
                            {"name": "AO", "primitiveType": "Line", "points": []}
                        ]
                    }
                },
            ),
        ]
    )
    client = DCSServerBotClient(session, "http://127.0.0.1:9876", "secret")

    bullseyes = await client.async_get_mission_bullseyes("Training")
    drawings = await client.async_get_mission_drawings("Training")

    assert bullseyes[0]["coalition"] == "blue"
    assert drawings["Author"][0]["name"] == "AO"
    assert all(request[2]["timeout"].total == 15 for request in session.requests)
