"""
db.py — Acces base de donnees Turso via libsql (embedded replica).

Le package "libsql" utilise une API synchrone sqlite3-compatible.
On l'execute dans un thread executor pour ne pas bloquer asyncio.

Embedded replica = fichier SQLite local synchronise avec Turso :
  - Lectures : locales (rapide, offline-capable)
  - Ecritures : envoyees vers Turso via HTTPS
"""
from __future__ import annotations
import asyncio
import functools
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import libsql

from src import config

_LOCAL_DB = os.path.join(
    os.path.dirname(__file__), "..", "data", "local_cache", "turso_replica.db"
)

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Database:
    """
    Wrapper async autour de libsql embedded replica Turso.
    Toutes les methodes publiques sont async.
    """

    def __init__(self) -> None:
        self._conn: Optional[libsql.Connection] = None

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(_LOCAL_DB), exist_ok=True)
        loop = asyncio.get_event_loop()
        self._conn = await loop.run_in_executor(
            None,
            functools.partial(
                libsql.connect,
                _LOCAL_DB,
                sync_url=config.TURSO_DATABASE_URL,
                auth_token=config.TURSO_AUTH_TOKEN,
            ),
        )
        await self._sync()

    async def close(self) -> None:
        if self._conn:
            await self._sync()

    async def _sync(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._conn.sync)

    async def _execute(self, sql: str, args: tuple = ()) -> tuple[list, Any]:
        """Execute SQL et retourne (rows, description)."""
        loop = asyncio.get_event_loop()

        def _do():
            cur = self._conn.execute(sql, list(args))
            self._conn.commit()
            try:
                rows = cur.fetchall()
                desc = cur.description
            except Exception:
                rows, desc = [], None
            return rows, desc

        return await loop.run_in_executor(None, _do)

    # --- Schema

    async def init_schema(self) -> None:
        schema_path = Path(__file__).parent.parent / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            await self._execute(stmt)
        await self._sync()
        print("Schema initialise avec succes.")

    # --- Players

    async def upsert_player(self, data: dict[str, Any]) -> None:
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
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        rows, desc = await self._execute("SELECT * FROM players WHERE tag = ?", (tag,))
        if rows and desc:
            cols = [d[0] for d in desc]
            return dict(zip(cols, rows[0]))
        return None

    # --- Clans

    async def upsert_clan(self, data: dict[str, Any]) -> None:
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
            "INSERT INTO player_queue (tag, priority, source, depth) VALUES (?,?,?,?) ON CONFLICT(tag) DO NOTHING",
            (tag, priority, source, depth),
        )

    async def enqueue_clan(self, tag: str, source: str, depth: int, priority: int = 50) -> None:
        await self._execute(
            "INSERT INTO clan_queue (tag, priority, source, depth) VALUES (?,?,?,?) ON CONFLICT(tag) DO NOTHING",
            (tag, priority, source, depth),
        )

    async def get_next_players(self, limit: int = 10) -> list[dict[str, Any]]:
        rows, desc = await self._execute(
            "SELECT tag, priority, source, depth, attempts FROM player_queue WHERE next_try_at <= ? ORDER BY priority DESC, next_try_at ASC LIMIT ?",
            (_now_iso(), limit),
        )
        if not rows or not desc:
            return []
        cols = [d[0] for d in desc]
        return [dict(zip(cols, row)) for row in rows]

    async def get_next_clans(self, limit: int = 10) -> list[dict[str, Any]]:
        rows, desc = await self._execute(
            "SELECT tag, priority, source, depth, attempts FROM clan_queue WHERE next_try_at <= ? ORDER BY priority DESC, next_try_at ASC LIMIT ?",
            (_now_iso(), limit),
        )
        if not rows or not desc:
            return []
        cols = [d[0] for d in desc]
        return [dict(zip(cols, row)) for row in rows]

    async def remove_player_from_queue(self, tag: str) -> None:
        await self._execute("DELETE FROM player_queue WHERE tag = ?", (tag,))

    async def remove_clan_from_queue(self, tag: str) -> None:
        await self._execute("DELETE FROM clan_queue WHERE tag = ?", (tag,))

    async def increase_player_attempt(self, tag: str) -> None:
        await self._execute(
            "UPDATE player_queue SET attempts = attempts + 1, next_try_at = datetime('now', '+30 minutes') WHERE tag = ?",
            (tag,),
        )

    async def increase_clan_attempt(self, tag: str) -> None:
        await self._execute(
            "UPDATE clan_queue SET attempts = attempts + 1, next_try_at = datetime('now', '+30 minutes') WHERE tag = ?",
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

    async def _count(self, table: str) -> int:
        rows, _ = await self._execute(f"SELECT COUNT(*) FROM {table}")
        return rows[0][0] if rows else 0

    async def count_players(self) -> int:
        return await self._count("players")

    async def count_clans(self) -> int:
        return await self._count("clans")

    async def count_battles(self) -> int:
        return await self._count("battle_summaries")

    async def count_player_queue(self) -> int:
        return await self._count("player_queue")

    async def count_clan_queue(self) -> int:
        return await self._count("clan_queue")

    async def activity_breakdown(self) -> dict[str, int]:
        rows, _ = await self._execute(
            "SELECT activity_status, COUNT(*) FROM players GROUP BY activity_status"
        )
        return {row[0]: row[1] for row in rows} if rows else {}

    async def update_crawl_stat(self, key: str, value: str) -> None:
        await self._execute(
            "INSERT INTO crawl_stats (stat_key, stat_value) VALUES (?,?)", (key, value)
        )
