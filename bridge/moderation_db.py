"""Trusted local database helper for the DCS HA moderation bridge."""

from __future__ import annotations

import contextlib
import io
import json
import pickle
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

import psutil
import psycopg


def database_url(root: Path) -> str:
    """Build the runtime URL using DCSServerBot's protected local secret."""
    nodes = (root / "config" / "nodes.yaml").read_text(encoding="utf-8")
    match = re.search(r"url:\s*(?:>-\s*)?(postgres(?:ql)?://[^\s#]+)", nodes)
    if not match:
        raise RuntimeError("Database URL was not found in nodes.yaml")
    with (root / "config" / ".secret" / "database.pkl").open("rb") as handle:
        password = str(pickle.load(handle))  # noqa: S301 - trusted bot-owned file
    return match.group(1).replace("SECRET", quote(password, safe=""))


def resolve_ucid(connection: psycopg.Connection, player_name: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ucid FROM players WHERE name = %s ORDER BY last_seen DESC LIMIT 1",
            (player_name,),
        )
        row = cursor.fetchone()
    if not row:
        raise RuntimeError("Player UCID was not found")
    return str(row[0])


def json_value(value):
    """Convert PostgreSQL-native values to safe JSON values."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def rows_as_dicts(cursor) -> list[dict]:
    """Return cursor rows as dictionaries without exposing database metadata."""
    columns = [item.name for item in cursor.description]
    return [
        {columns[index]: json_value(value) for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]


def table_exists(connection: psycopg.Connection, table_name: str) -> bool:
    """Return whether a public table exists without raising on older bot versions."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        return cursor.fetchone()[0] is not None


def firewall_profiles() -> dict:
    """Return read-only Windows Firewall profile and DCS block-rule data."""
    command = r"""
$profiles = Get-NetFirewallProfile | Select-Object Name, Enabled
$blocked = @()
Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
  Where-Object { $_.DisplayName -like 'DCS-blocked*' -or $_.Name -like 'DCS-blocked*' } |
  ForEach-Object {
    $rule = $_
    Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $rule -ErrorAction SilentlyContinue |
      ForEach-Object {
        if ($_.RemoteAddress -and $_.RemoteAddress -ne 'Any') {
          $blocked += @($_.RemoteAddress)
        }
      }
  }
[pscustomobject]@{
  profiles = @($profiles)
  blocked_ips = @($blocked | Sort-Object -Unique)
} | ConvertTo-Json -Depth 5 -Compress
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        payload = json.loads(result.stdout.strip())
        profiles = payload.get("profiles") or []
        if isinstance(profiles, dict):
            profiles = [profiles]
        return {
            "profiles": [
                {"name": str(item.get("Name")), "enabled": bool(item.get("Enabled"))}
                for item in profiles
                if isinstance(item, dict)
            ],
            "blocked_ips": [str(item) for item in payload.get("blocked_ips") or []],
        }
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, json.JSONDecodeError):
        return {"profiles": [], "blocked_ips": [], "read_error": True}


def system_snapshot(root: Path) -> dict:
    """Return compact CPU topology, DCS affinities and firewall state."""
    sys.path.insert(0, str(root))
    with contextlib.redirect_stdout(io.StringIO()):
        from core.process.processmanager import ProcessManager

        exported = ProcessManager().export_topology()

    cpu_sets = exported.get("cpu_sets") or []
    numa: dict[int, list[int]] = {}
    llc: dict[tuple[int, int], list[int]] = {}
    for item in cpu_sets:
        logical = int(item.get("Logical Processor Index", 0))
        numa_id = int(item.get("Numa Node Index", 0))
        llc_id = int(item.get("Last Level Cache Index", 0))
        numa.setdefault(numa_id, []).append(logical)
        llc.setdefault((numa_id, llc_id), []).append(logical)

    processes = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if str(process.info.get("name") or "").casefold() != "dcs_server.exe":
                continue
            command = " ".join(process.info.get("cmdline") or [])
            match = re.search(r"(?:^|\s)-w\s+([^\s\"]+)", command, flags=re.IGNORECASE)
            instance = match.group(1) if match else "unknown"
            server_name = None
            settings = Path.home() / "Saved Games" / instance / "Config" / "serverSettings.lua"
            if settings.exists():
                content = settings.read_text(encoding="utf-8", errors="replace")
                name_match = re.search(
                    r'(?:\[\s*["\']name["\']\s*\]|\bname)\s*=\s*["\']([^"\']+)',
                    content,
                )
                if name_match:
                    server_name = name_match.group(1)
            cores = sorted(process.cpu_affinity())
            processes.append(
                {
                    "pid": int(process.info["pid"]),
                    "instance": instance,
                    "server_name": server_name,
                    "logical_processors": cores,
                    "numa_nodes": sorted(
                        node_id
                        for node_id, members in numa.items()
                        if set(cores).intersection(members)
                    ),
                }
            )
        except (psutil.Error, OSError, ValueError):
            continue

    firewall = firewall_profiles()
    return {
        "status": "ok",
        "topology": {
            "cpu_name": exported.get("cpu_name"),
            "logical_processors": len(cpu_sets),
            "physical_cores": len({item.get("Core Index") for item in cpu_sets}),
            "numa_nodes": [
                {"id": node_id, "logical_processors": sorted(members)}
                for node_id, members in sorted(numa.items())
            ],
            "llc_groups": [
                {
                    "numa_node": key[0],
                    "id": key[1],
                    "logical_processors": sorted(members),
                }
                for key, members in sorted(llc.items())
            ],
            "dies": exported.get("die") or [],
        },
        "process_affinity": processes,
        "firewall": firewall,
    }


def operations_snapshot(connection: psycopg.Connection) -> dict:
    """Collect read-only Operations Center telemetry and mission history."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (server_name)
                       server_name, mission_id, users, status, mission_time,
                       cpu, mem_total, mem_ram, fps, ping,
                       bytes_sent, bytes_recv, time
                FROM serverstats
                ORDER BY server_name, time DESC
            ), averages AS (
                SELECT server_name,
                       ROUND(AVG(fps), 2) AS fps_avg_15m,
                       ROUND(AVG(cpu), 2) AS cpu_avg_15m,
                       ROUND(AVG(mem_ram) / POWER(1024.0, 3), 2)
                           AS memory_avg_15m_gib
                FROM serverstats
                WHERE time >= (NOW() AT TIME ZONE 'utc') - INTERVAL '15 minutes'
                GROUP BY server_name
            )
            SELECT l.server_name, l.mission_id, l.users, l.status, l.mission_time,
                   ROUND(l.cpu, 2) AS cpu,
                   ROUND(l.mem_ram / POWER(1024.0, 3), 2) AS memory_gib,
                   ROUND(l.mem_total / POWER(1024.0, 3), 2) AS virtual_memory_gib,
                   ROUND(l.fps, 2) AS fps, ROUND(l.ping, 2) AS ping,
                   ROUND(l.bytes_sent, 2) AS bytes_sent,
                   ROUND(l.bytes_recv, 2) AS bytes_recv, l.time,
                   ROUND(EXTRACT(EPOCH FROM ((NOW() AT TIME ZONE 'utc') - l.time)))::INTEGER
                       AS sample_age_seconds,
                   a.fps_avg_15m, a.cpu_avg_15m, a.memory_avg_15m_gib
            FROM latest l
            LEFT JOIN averages a USING (server_name)
            ORDER BY l.server_name
            """
        )
        performance_rows = rows_as_dicts(cursor)

        cursor.execute(
            """
            SELECT m.id, m.server_name, m.mission_name, m.mission_theatre,
                   m.mission_start, m.mission_end,
                   ROUND(EXTRACT(EPOCH FROM (
                       COALESCE(m.mission_end, NOW() AT TIME ZONE 'utc')
                       - m.mission_start
                   )))::INTEGER
                       AS duration_seconds,
                   COUNT(DISTINCT s.player_ucid)::INTEGER AS unique_pilots,
                   COUNT(s.hop_on)::INTEGER AS sorties,
                   COALESCE(SUM(s.kills), 0)::INTEGER AS kills,
                   COALESCE(SUM(s.pvp), 0)::INTEGER AS pvp_kills,
                   COALESCE(SUM(s.deaths), 0)::INTEGER AS deaths,
                   COALESCE(SUM(s.takeoffs), 0)::INTEGER AS takeoffs,
                   COALESCE(SUM(s.landings), 0)::INTEGER AS landings,
                   COALESCE(SUM(s.crashes), 0)::INTEGER AS crashes,
                   COALESCE(SUM(s.ejections), 0)::INTEGER AS ejections,
                   COALESCE(SUM(s.teamkills), 0)::INTEGER AS teamkills
            FROM missions m
            LEFT JOIN statistics s ON s.mission_id = m.id
            GROUP BY m.id, m.server_name, m.mission_name, m.mission_theatre,
                     m.mission_start, m.mission_end
            ORDER BY m.mission_start DESC
            LIMIT 20
            """
        )
        missions = rows_as_dicts(cursor)

        cursor.execute(
            """
            SELECT name
            FROM players
            WHERE vip = TRUE AND name IS NOT NULL
            ORDER BY LOWER(name)
            """
        )
        vip_players = [str(row[0]) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT ms.id, m.server_name, m.mission_name, ms.event,
                   COALESCE(pi.name, ms.init_type, ms.init_id) AS initiator,
                   ms.init_side, ms.init_type,
                   COALESCE(pt.name, ms.target_type, ms.target_id) AS target,
                   ms.target_side, ms.target_type, ms.weapon, ms.place,
                   ms.comment, ms.time
            FROM missionstats ms
            JOIN missions m ON m.id = ms.mission_id
            LEFT JOIN players pi ON pi.ucid = ms.init_id
            LEFT JOIN players pt ON pt.ucid = ms.target_id
            WHERE ms.event IN (
                'S_EVENT_TAKEOFF', 'S_EVENT_LAND', 'S_EVENT_HIT',
                'S_EVENT_KILL', 'S_EVENT_DEAD', 'S_EVENT_CRASH',
                'S_EVENT_EJECTION'
            )
            ORDER BY ms.time DESC, ms.id DESC
            LIMIT 100
            """
        )
        events = rows_as_dicts(cursor)

        firewall: dict = {
            "service_configured": table_exists(connection, "port_traffic"),
            "under_attack": False,
            "ports": [],
        }
        if firewall["service_configured"]:
            cursor.execute(
                """
                SELECT DISTINCT ON (server_name, port, protocol)
                       server_name, port, protocol, bytes_in, bytes_out,
                       packets_in, packets_out, unique_ips, connections,
                       non_player_udp_ips, players, under_attack, time
                FROM port_traffic
                ORDER BY server_name, port, protocol, time DESC
                """
            )
            ports = rows_as_dicts(cursor)
            firewall["ports"] = ports
            firewall["under_attack"] = any(bool(item.get("under_attack")) for item in ports)

    return {
        "status": "ok",
        "generated_at": datetime.now(UTC).isoformat(),
        "performance": {str(row.pop("server_name")): row for row in performance_rows},
        "missions": missions,
        "vip_players": vip_players,
        "events": events,
        "firewall": firewall,
    }


def main() -> None:
    request = json.load(sys.stdin)
    root = Path(request.get("root") or r"G:\DCSServerBot")
    action = str(request.get("action") or "")
    with psycopg.connect(database_url(root)) as connection:
        if action == "health":
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            result = {"status": "ok"}
        elif action == "operations_snapshot":
            result = operations_snapshot(connection)
        elif action == "system_snapshot":
            result = system_snapshot(root)
        elif action == "ban":
            player_name = str(request["player_name"])
            reason = str(request.get("reason") or "Moderation by Home Assistant")
            days = int(request.get("days") or 0)
            if days < 0 or days > 3650:
                raise RuntimeError("Invalid ban duration")
            ucid = resolve_ucid(connection, player_name)
            until = (
                datetime.now(UTC).replace(tzinfo=None) + timedelta(days=days)
                if days
                else datetime(9999, 12, 31)
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO bans (ucid, banned_by, reason, banned_until)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ucid) DO UPDATE SET
                      banned_by = excluded.banned_by,
                      reason = excluded.reason,
                      banned_at = excluded.banned_at,
                      banned_until = excluded.banned_until
                    """,
                    (ucid, "Home Assistant", reason, until),
                )
            result = {"status": "ok", "ucid": ucid}
        elif action == "unban":
            ucid = resolve_ucid(connection, str(request["player_name"]))
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE bans SET banned_until = NOW() AT TIME ZONE 'UTC' WHERE ucid = %s",
                    (ucid,),
                )
            result = {"status": "ok", "ucid": ucid}
        else:
            raise RuntimeError("Unknown database action")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # process boundary returns a sanitized message
        print(json.dumps({"status": "error", "error": str(error)}))
        raise SystemExit(1) from error
