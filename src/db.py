"""
db.py — Acces base de données Turso (libSQL / SQLite compatible).
Tous les upserts sont idempotents via INSERT ... ON CONFLICT DO UPDATE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import libsql_client
from rich.console import Console

from src import config

console = Console()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Database:
    """
    Wrapper async autour du client libSQL (Turso).

    Usage:
        db = Database()
        await db.connect()
        await db.init_schema()
        ...
        await db.close()
    """

    def __init__(self) -> None:
        self._client: Optional[libsql_client.Client] = None

    async def connect(self) -> None:
        self._client = libsql_client.create_client(
            url=config.TURSO_DATABASE_URL,
            auth_token=config.TURSO_AUTH_TOKEN,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    async def _execute(self, sql: str, args: tuple = ()) -> Any:
        assert self._client, "Database non connectee — appeler connect() d abord"
        return await self._client.execute(
            libsql_client.Statement(sql, list(args))
        )

    # --- Schema

    async def init_schema(self) -> None:
        """Execute schema.sql pour creer les tables et index."""
        schema_path = Path(__file__).parent.parent / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            await self._execute(stmt)
        console.print("[bold green]Schema initialise avec succes.[/bold green]")

    # --- Players

    async def upsert_player(self, data: dict[str, Any]) -> None:
        """Insere ou met a jour un joueur. Preserve les donnees importantes existantes."""
        await self._execute(
            """
            INSERT INTO players (
                tag, name, clan_tag, clan_name,
                trophies, best_trophies, exp_level, arena_id,
                battle_count, wins, losses, three_crown_wins,
                donations, donations_received,
                last_seen_api, last_battle_time,
                activity_status, activity_score,
                discovered_from, discovery_depth,
                last_profile_scan_at, last_battlelog_scan_at, next_scan_at,
                updated_at
            ) VALUES (
                ?,?,?,?,
                ?,?,?,?,
                ?,?,?,?,
                ?,?,
                ?,?,
                ?,?,
                ?,?,
                ?,?,?,
                ?
            )
            ON CONFLICT(tag) DO UPDATE SET
                name                   = COALESCE(excluded.name, name),
                clan_tag               = COALESCE(excluded.clan_tag, clan_tag),
                clan_name              = COALESCE(excluded.clan_name, clan_name),
                trophies               = COALESCE(excluded.trophies, trophies),
                best_trophies          = COALESCE(excluded.best_trophies, best_trophies),
                exp_level              = COALESCE(excluded.exp_level, exp_level),
                arena_id               = COALESCE(excluded.arena_id, arena_id),
                battle_count           = COALESCE(excluded.battle_count, battle_count),
                wins                   = COALESCE(excluded.wins, wins),
                losses                 = COALESCE(excluded.losses, losses),
                three_crown_wins       = COALESCE(excluded.three_crown_wins, three_crown_wins),
                donations              = COALESCE(excluded.donations, donations),
                donations_received     = COALESCE(excluded.donations_received, donations_received),
                last_seen_api          = COALESCE(excluded.last_seen_api, last_seen_api),
                last_battle_time       = COALESCE(excluded.last_battle_time, last_battle_time),
                activity_status        = COALESCE(excluded.activity_status, activity_status),
                activity_score         = COALESCE(excluded.activity_score, activity_score),
                last_profile_scan_at   = COALESCE(excluded.last_profile_scan_at, last_profile_scan_at),
                last_battlelog_scan_at = COALESCE(excluded.last_battlelog_scan_at, last_battlelog_scan_at),
                next_scan_at           = COALESCE(excluded.next_scan_at, next_scan_at),
                updated_at             = excluded.updated_at
            """,
            (
                data.get("tag"), data.get("name"), data.get("clan_tag"), data.get("clan_name"),
                data.get("trophies"), data.get("best_trophies"), data.get("exp_level"), data.get("arena_id"),
                data.get("battle_count"), data.get("wins"), data.get("losses"), data.get("three_crown_wins"),
                data.get("donations"), data.get("donations_received"),
                data.get("last_seen_api"), data.get("last_battle_time"),
                data.get("activity_status", "unknown"), data.get("activity_score", 0),
                data.get("discovered_from"), data.get("discovery_depth", 0),
                data.get("last_profile_scan_at"), data.get("last_battlelog_scan_at"), data.get("next_scan_at"),
                _now_iso(),
            ),
        )

    async def get_player(self, tag: str) -> Optional[dict[str, Any]]:
        """Recupere un joueur depuis la DB, ou None."""
        result = await self._execute("SELECT * FROM players WHERE tag = ?", (tag,))
        if result.rows:
            cols = [c.name for c in result.columns]
            return dict(zip(cols, result.rows[0]))
        return None

    # --- Clans

    async def upsert_clan(self, data: dict[str, Any]) -> None:
        """Insere ou met a jour un clan. Idempotent."""
        await self._execute(
            """
            INSERT INTO clans (
                tag, name, location_id, members, clan_score, required_trophies,
                last_members_scan_at, next_members_scan_at,
                discovered_from, discovery_depth, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tag) DO UPDATE SET
                name                 = COALESCE(excluded.name, name),
                location_id          = COALESCE(excluded.location_id, location_id),
                members              = COALESCE(excluded.members, members),
                clan_score           = COALESCE(excluded.clan_score, clan_score),
                required_trophies    = COALESCE(excluded.required_trophies, required_trophies),
                last_members_scan_at = COALESCE(excluded.last_members_scan_at, last_members_scan_at),
                next_members_scan_at = COALESCE(excluded.next_members_scan_at, next_members_scan_at),
                updated_at           = excluded.updated_at
            """,
            (
                data.get("tag"), data.get("name"),
                data.get("location_id"), data.get("members"),
                data.get("clan_score"), data.get("required_trophies"),
                data.get("last_members_scan_at"), data.get("next_members_scan_at"),
                data.get("discovered_from"), data.get("discovery_depth", 0),
                _now_iso(),
            ),
        )

    # --- Queues

    async def enqueue_player(self, tag: str, source: str, depth: int, priority: int = 50) -> None:
        await self._execute(
            """
            INSERT INTO player_queue (tag, priority, source, depth)
            VALUES (?,?,?,?)
            ON CONFLICT(tag) DO NOTHING
            """,
            (tag, priority, source, depth),
        )

    async def enqueue_clan(self, tag: str, source: str, depth: int, priority: int = 50) -> None:
        await self._execute(
            """
            INSERT INTO clan_queue (tag, priority, source, depth)
            VALUES (?,?,?,?)
            ON CONFLICT(tag) DO NOTHING
            """,
            (tag, priority, source, depth),
        )

    async def get_next_players(self, limit: int = 10) -> list[dict[str, Any]]:
        result = await self._execute(
            """
            SELECT tag, priority, source, depth, attempts
            FROM player_queue
            WHERE next_try_at <= ?
            ORDER BY priority DESC, next_try_at ASC
            LIMIT ?
            """,
            (_now_iso(), limit),
        )
        cols = [c.name for c in result.columns]
        return [dict(zip(cols, row)) for row in result.rows]

    async def get_next_clans(self, limit: int = 10) -> list[dict[str, Any]]:
        result = await self._execute(
            """
            SELECT tag, priority, source, depth, attempts
            FROM clan_queue
            WHERE next_try_at <= ?
            ORDER BY priority DESC, next_try_at ASC
            LIMIT ?
            """,
            (_now_iso(), limit),
        )
        cols = [c.name for c in result.columns]
        return [dict(zip(cols, row)) for row in result.rows]

    async def remove_player_from_queue(self, tag: str) -> None:
        await self._execute("DELETE FROM player_queue WHERE tag = ?", (tag,))

    async def remove_clan_from_queue(self, tag: str) -> None:
        await self._execute("DELETE FROM clan_queue WHERE tag = ?", (tag,))

    async def increase_player_attempt(self, tag: str) -> None:
        await self._execute(
            """
            UPDATE player_queue
            SET attempts    = attempts + 1,
                next_try_at = datetime('now', '+30 minutes')
            WHERE tag = ?
            """,
            (tag,),
        )

    async def increase_clan_attempt(self, tag: str) -> None:
        await self._execute(
            """
            UPDATE clan_queue
            SET attempts    = attempts + 1,
                next_try_at = datetime('now', '+30 minutes')
            WHERE tag = ?
            """,
            (tag,),
        )

    # --- Battle summaries

    async def insert_battle_summary(self, data: dict[str, Any]) -> None:
        await self._execute(
            """
            INSERT INTO battle_summaries (
                battle_id, battle_time, battle_type, game_mode,
                player_tag, opponent_tag,
                player_crowns, opponent_crowns, result,
                player_deck_hash, opponent_deck_hash, raw_r2_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(battle_id) DO NOTHING
            """,
            (
                data.get("battle_id"), data.get("battle_time"),
                data.get("battle_type"), data.get("game_mode"),
                data.get("player_tag"), data.get("opponent_tag"),
                data.get("player_crowns"), data.get("opponent_crowns"),
                data.get("result"),
                data.get("player_deck_hash"), data.get("opponent_deck_hash"),
                data.get("raw_r2_key"),
            ),
        )

    # --- Stats

    async def count_players(self) -> int:
        result = await self._execute("SELECT COUNT(*) FROM players")
        return result.rows[0][0] if result.rows else 0

    async def count_clans(self) -> int:
        result = await self._execute("SELECT COUNT(*) FROM clans")
        return result.rows[0][0] if result.rows else 0

    async def count_battles(self) -> int:
        result = await self._execute("SELECT COUNT(*) FROM battle_summaries")
        return result.rows[0][0] if result.rows else 0

    async def count_player_queue(self) -> int:
        result = await self._execute("SELECT COUNT(*) FROM player_queue")
        return result.rows[0][0] if result.rows else 0

    async def count_clan_queue(self) -> int:
        result = await self._execute("SELECT COUNT(*) FROM clan_queue")
        return result.rows[0][0] if result.rows else 0

    async def activity_breakdown(self) -> dict[str, int]:
        result = await self._execute(
            "SELECT activity_status, COUNT(*) FROM players GROUP BY activity_status"
        )
        return {row[0]: row[1] for row in result.rows}

    async def update_crawl_stat(self, key: str, value: str) -> None:
        await self._execute(
            "INSERT INTO crawl_stats (stat_key, stat_value) VALUES (?,?)",
            (key, value),
        )
