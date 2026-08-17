"""Trusted local database helper for the DCS HA moderation bridge."""

from __future__ import annotations

import json
import pickle
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import psycopg


def database_url(root: Path) -> str:
    """Build the runtime URL using DCSServerBot's protected local secret."""
    nodes = (root / "config" / "nodes.yaml").read_text(encoding="utf-8")
    match = re.search(
        r"url:\s*(?:>-\s*)?(postgres(?:ql)?://[^\s#]+)", nodes
    )
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
                    "UPDATE bans SET banned_until = NOW() AT TIME ZONE 'UTC' "
                    "WHERE ucid = %s",
                    (ucid,),
                )
            result = {"status": "ok", "ucid": ucid}
        else:
            raise RuntimeError("Unknown database action")
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # process boundary returns a sanitized message
        print(json.dumps({"status": "error", "error": str(error)}))
        raise SystemExit(1) from error

