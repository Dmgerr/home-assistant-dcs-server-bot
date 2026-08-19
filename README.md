# DCS Server Bot Operations Center for Home Assistant

[![HACS validation](https://github.com/Dmgerr/home-assistant-dcs-server-bot/actions/workflows/validate.yml/badge.svg)](https://github.com/Dmgerr/home-assistant-dcs-server-bot/actions/workflows/validate.yml)
[![Tests](https://github.com/Dmgerr/home-assistant-dcs-server-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/Dmgerr/home-assistant-dcs-server-bot/actions/workflows/tests.yml)

A local, asynchronous Home Assistant integration for
[DCSServerBot](https://github.com/Special-K-s-Flightsim-Bots/DCSServerBot).
It turns the bot's RestAPI into devices, entities, events and optional control
actions suitable for a dedicated Operations Center dashboard.

## Features

- UI-based setup and reauthentication
- One Home Assistant device per DCS server
- API connectivity, server state and aggregate server/player counters
- Current mission, theatre, mission time, scheduled restart and weather
- Active player details and loaded DCSServerBot extensions
- Live airbase list and a selectable warehouse inventory
- Kill, K/D and category leaderboards
- DCS FPS, CPU, memory and ping telemetry with debounced health alerts
- Mission AAR summaries and the last 20 mission records
- Events for mission completion, health alerts, server-state changes and players joining/leaving
- Optional start, stop, restart, mission pause/resume/restart and mission selection
- Optional player selector, kick and persistent ban/unban through a separate bridge
- Redacted diagnostics — API keys, server passwords and addresses are not exported
- Polish, English, German, French and Spanish setup translations

Control and moderation are **disabled by default**. Monitoring never calls a
state-changing endpoint. Each capability has to be enabled explicitly in the
integration's options.

## Requirements

- Home Assistant 2025.1 or newer
- DCSServerBot 3.x with the optional `restapi` plugin
- A `config/plugins/userstats.yaml` file so DCSServerBot refreshes its
  materialized statistics views
- Network access from Home Assistant to the DCSServerBot WebService

## DCSServerBot configuration

Add the optional plugin to `config/main.yaml`:

```yaml
opt_plugins:
  - restapi
```

Create `config/services/webservice.yaml`:

```yaml
DEFAULT:
  listen: 0.0.0.0
  port: 9876
  debug: false
```

Create `config/plugins/restapi.yaml` with a long, unique secret:

```yaml
DEFAULT:
  api_key: "replace-with-a-long-random-secret"
  endpoints:
    servers:
      include_weather: true
```

Create `config/plugins/userstats.yaml` as well. This file is required even if
you do not use the UserStats Discord commands. DCSServerBot loads the plugin by
default, but only starts its hourly statistics-view refresh task when the
plugin has a configuration file. Without it, `/serverstats` keeps returning
old sortie, kill, death and playtime totals while raw flight data continues to
be recorded.

```yaml
DEFAULT:
  wipe_stats_on_leave: true
```

A ready-to-copy example is available at
[`docs/dcssb-userstats.yaml`](docs/dcssb-userstats.yaml). Do not add
`userstats` to `opt_plugins`; only the configuration file is needed.

Restart **DCSServerBot**, not the DCS game server. Permit TCP 9876 only from
your trusted LAN or, preferably, only from the Home Assistant host. Never
forward this port to the internet: the upstream API includes administrative
endpoints.

## Installation with HACS

1. Open HACS → Integrations → three-dot menu → Custom repositories.
2. Add `Dmgerr/home-assistant-dcs-server-bot` as an Integration.
3. Download **DCS Server Bot Operations Center**.
4. Restart Home Assistant.
5. Open Settings → Devices & services → Add integration.
6. Search for `DCS Server Bot Operations Center`.
7. Enter the WebService URL, for example `http://192.168.1.47:9876`, and its API key.

## Entities

The hub device provides API connectivity and aggregate counts. Each server
provides status, running/paused state, players, mission, mission uptime,
temperature, wind, extensions, address and scheduled restart.

When control is enabled, the server device also receives buttons and a mission
selector. Dashboard buttons should always use a confirmation dialog.

If DCSServerBot times out while replacing the current mission during a mission
restart, the integration retries through the bot's server restart endpoint. This
stop/start fallback reloads the same mission without modifying DCSServerBot.

When moderation is enabled, each server also receives an active-player selector,
kick/ban buttons, performance telemetry, mission history and VIP metadata. Because
the upstream RestAPI has no moderation or historical telemetry endpoints, this
requires the optional, separately secured [`bridge`](bridge/README.md). The bridge
reads the existing DCSServerBot database and does not modify the bot.

## Events

- `dcs_server_bot_server_status_changed`
- `dcs_server_bot_player_joined`
- `dcs_server_bot_player_left`
- `dcs_server_bot_important_player_joined`
- `dcs_server_bot_mission_ended`
- `dcs_server_bot_performance_alert`

Each event contains `server_name`; status events include `old_status` and
`new_status`, while player events include `player`. Mission completion includes
the AAR `summary`. Performance events include `alert_type` (`low_fps` or
`mission_stalled`) and the latest FPS, CPU and memory values.

## Actions

- `dcs_server_bot.start_server`
- `dcs_server_bot.stop_server`
- `dcs_server_bot.restart_server`
- `dcs_server_bot.pause_mission`
- `dcs_server_bot.resume_mission`
- `dcs_server_bot.restart_mission`
- `dcs_server_bot.load_mission`
- `dcs_server_bot.kick_player`
- `dcs_server_bot.ban_player`
- `dcs_server_bot.unban_player`

Actions accept `server_name`; `load_mission` also requires `mission_name`.
`entry_id` is optional and is useful when several bots contain identically
named servers.

Moderation actions accept `player_name` and an optional `reason`. Kick also
requires `server_name`; ban accepts `days` from 0 to 3650, where 0 is permanent.

## Dashboard

The repository contains a native, responsive dashboard example in
[`dashboards/operations-center.yaml`](dashboards/operations-center.yaml).
Entity IDs depend on the names assigned by Home Assistant, so review them after
setup before importing the example.

The full dashboard is organised into six views: live mission, pilots, airbases
and warehouses, statistics and rankings, server performance, and AAR/history.
Home Assistant automations can use the events above for end-of-mission reports,
health alerts and important-player notifications; no voice assistant is needed.

## Troubleshooting

- **Cannot connect:** confirm TCP 9876 is listening and reachable from the HA host.
- **401/403:** update the API key with the integration reauthentication flow.
- **No control entities:** enable controls under Settings → Devices & services →
  DCS Server Bot Operations Center → Configure.
- **No moderation entities:** start and secure the companion bridge, then enable
  moderation and provide its URL in the integration options.
- **Some servers are missing:** check the RestAPI `servers` endpoint filters.
- **Sorties, kills, deaths or playtime never update:** make sure
  `config/plugins/userstats.yaml` exists, then restart DCSServerBot. Existing
  DCS game-server processes and missions do not need to be restarted.
- Download diagnostics from the integration menu before opening an issue.

## Security

This project is not affiliated with Eagle Dynamics or the DCSServerBot authors.
Home Assistant stores the API key in its config entry. The integration never
creates entities from the server password returned by DCSServerBot and removes
that field immediately after receiving a response.

## License

MIT
