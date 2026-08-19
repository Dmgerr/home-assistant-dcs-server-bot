# Optional moderation bridge

DCSServerBot's official RestAPI does not currently expose player kick or ban
endpoints. This small companion process adds only those operations without
changing or rebuilding DCSServerBot.

The bridge:

- reuses the RestAPI key from `config/plugins/restapi.yaml`;
- resolves the selected server through the official `/servers` endpoint;
- sends kick/ban commands only to local DCS UDP ports;
- records persistent bans in DCSServerBot's existing PostgreSQL `bans` table;
- maintains an append-only moderation audit log;
- rejects clients outside its explicit IP allowlist.
- exposes a read-only cached Operations Center snapshot with DCS performance,
  VIP-player names and aggregated mission history;

## Requirements

- Node.js 20 or newer;
- the Python environment used by DCSServerBot (with `psycopg`);
- the bridge must run on the DCSServerBot host;
- the Home Assistant host must be listed in `allowed_ips`.

## Setup

1. Copy `bridge.config.example.json` to `bridge.config.json`.
2. Set the bind address, Home Assistant IP and DCSServerBot Python path.
3. If DCSServerBot is not in `G:\DCSServerBot`, set the `DCSBOT_ROOT`
   environment variable.
4. Start `node dcs_ha_moderation_bridge.js` under a restricted service account.
5. Permit the bridge TCP port only from the Home Assistant host.
6. In the integration options, enable player moderation and enter the bridge
   URL, for example `http://192.168.1.47:9877`.

The integration exposes an active-player selector, kick, one-day ban,
seven-day ban and permanent-ban buttons. Home Assistant dashboard buttons
should use confirmation dialogs. The `kick_player`, `ban_player` and
`unban_player` actions provide custom reasons and ban durations for advanced
automations.

`GET /operations/snapshot` uses the same API key and allowlist as moderation.
It is read-only and powers FPS/CPU/RAM/ping sensors, mission-stall detection,
VIP join events and AAR history. Results are cached for 15 seconds to avoid
unnecessary database load.

Never expose the RestAPI or the moderation bridge to the internet.
