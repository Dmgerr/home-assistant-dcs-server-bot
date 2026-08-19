"""Trusted local database helper for the DCS HA moderation bridge."""

from __future__ import annotations

import json
import pickle
import re
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

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


def operations_snapshot(connection: psycopg.Connection) -> dict:
    """Collect read-only Operations Center telemetry and mission history."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (server_name)
                       server_name, mission_id, users, status, mission_time,
                       cpu, mem_total, mem_ram, fps, ping, time
                FROM serverstats
                ORDER BY server_name, time DESC
            ), averages AS (
                SELECT server_name,
                       ROUND(AVG(fps), 2) AS fps_avg_15m,
                       ROUND(AVG(cpu), 2) AS cpu_avg_15m,
                       ROUND(AVG(CASE WHEN mem_total > 0
                                      THEN mem_ram * 100.0 / mem_total END), 2)
                           AS memory_avg_15m
                FROM serverstats
                WHERE time >= (NOW() AT TIME ZONE 'utc') - INTERVAL '15 minutes'
                GROUP BY server_name
            )
            SELECT l.server_name, l.mission_id, l.users, l.status, l.mission_time,
                   ROUND(l.cpu, 2) AS cpu,
                   ROUND(CASE WHEN l.mem_total > 0
                              THEN l.mem_ram * 100.0 / l.mem_total END, 2)
                       AS memory_percent,
                   ROUND(l.fps, 2) AS fps, ROUND(l.ping, 2) AS ping, l.time,
                   ROUND(EXTRACT(EPOCH FROM ((NOW() AT TIME ZONE 'utc') - l.time)))::INTEGER
                       AS sample_age_seconds,
                   a.fps_avg_15m, a.cpu_avg_15m, a.memory_avg_15m
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

    return {
        "status": "ok",
        "generated_at": datetime.now(UTC).isoformat(),
        "performance": {str(row.pop("server_name")): row for row in performance_rows},
        "missions": missions,
        "vip_players": vip_players,
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
