"""
crawler.py — Moteur principal du crawler Clash Royale.

Decouverte BFS:
  seed -> battlelog -> clan -> membres -> battlelogs membres -> ...
  Borne par CRAWL_MAX_DEPTH et CRAWL_MAX_PLAYERS.

Reprise: les queues sont persistees dans Turso.
Ctrl+C arrete proprement, relancer reprend ou ca s'est arrete.
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box

from src import config
from src.clash_api import ClashRoyaleAPI, ClashAPIError
from src.db import Database
from src.r2_storage import R2Storage
from src.normalize import (
    normalize_tag, safe_tag_for_path,
    extract_tags_from_battlelog, deck_hash, make_battle_id,
)
from src.classifier import classify_player
from src.utils import run_with_semaphore

console = Console()


class Crawler:
    def __init__(self) -> None:
        self.db         = Database()
        self.r2         = R2Storage() if config.STORE_RAW_JSON else None
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
        self._api: Optional[ClashRoyaleAPI] = None

    async def run(self) -> None:
        await self.db.connect()
        console.print("[bold cyan]Clash Royale Crawler demarre[/bold cyan]")
        console.print(f"  Seed       : [green]{config.SEED_PLAYER_TAG}[/green]")
        console.print(f"  Max depth  : {config.CRAWL_MAX_DEPTH}")
        console.print(f"  Max joueurs: {config.CRAWL_MAX_PLAYERS}")
        console.print(f"  RPS max    : {config.MAX_RPS}")
        console.print(f"  Concurrence: {config.MAX_CONCURRENT_REQUESTS}")
        console.print(f"  Raw JSON R2: {config.STORE_RAW_JSON}")

        async with ClashRoyaleAPI() as api:
            self._api = api
            seed = normalize_tag(config.SEED_PLAYER_TAG)
            await self.db.enqueue_player(seed, source="seed", depth=0, priority=100)
            console.print(f"[green]Seed enqueue: {seed}[/green]")
            await self._main_loop()

        await self.db.close()
        console.print("[bold green]Crawler termine.[/bold green]")

    async def _main_loop(self) -> None:
        last_stats = 0.0
        while True:
            total = await self.db.count_players()
            if total >= config.CRAWL_MAX_PLAYERS:
                console.print(f"[bold yellow]Limite atteinte: {total} joueurs[/bold yellow]")
                break

            player_batch = await self.db.get_next_players(limit=config.MAX_CONCURRENT_REQUESTS)
            clan_batch   = await self.db.get_next_clans(limit=config.MAX_CONCURRENT_REQUESTS)

            if not player_batch and not clan_batch:
                console.print("[yellow]Queues vides — attente 30s...[/yellow]")
                await asyncio.sleep(30)
                continue

            tasks = (
                [run_with_semaphore(self._semaphore, self._scan_player, i["tag"], i["depth"]) for i in player_batch] +
                [run_with_semaphore(self._semaphore, self._scan_clan,   i["tag"], i["depth"]) for i in clan_batch]
            )
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    console.print(f"[red]Task error: {r}[/red]")

            now = time.monotonic()
            if now - last_stats > 60:
                await self._print_stats()
                last_stats = now

    async def _scan_player(self, tag: str, depth: int) -> None:
        tag  = normalize_tag(tag)
        safe = safe_tag_for_path(tag)
        console.print(f"[cyan]Scan joueur {tag} (depth={depth})[/cyan]")

        old_profile = await self.db.get_player(tag)

        try:
            profile = await self._api.get_player(tag)
        except ClashAPIError:
            await self.db.increase_player_attempt(tag)
            return

        if profile is None:
            console.print(f"[dim]Joueur introuvable: {tag}[/dim]")
            await self.db.remove_player_from_queue(tag)
            return

        if self.r2:
            try:
                self.r2.put_json_gz(self.r2.player_key(safe), profile)
            except Exception:
                pass

        clan_info = profile.get("clan") or {}
        if clan_info.get("tag") and depth + 1 <= config.CRAWL_MAX_DEPTH:
            await self.db.enqueue_clan(
                normalize_tag(clan_info["tag"]),
                source=f"player:{tag}", depth=depth + 1, priority=70,
            )

        battlelog = None
        battlelog_r2_key: Optional[str] = None
        try:
            battlelog = await self._api.get_player_battlelog(tag)
        except ClashAPIError:
            pass

        if battlelog is not None:
            if self.r2:
                try:
                    battlelog_r2_key = self.r2.put_json_gz(self.r2.battlelog_key(safe), battlelog)
                except Exception:
                    pass
            if depth + 1 <= config.CRAWL_MAX_DEPTH:
                for dtag in extract_tags_from_battlelog(battlelog):
                    if dtag != tag:
                        await self.db.enqueue_player(
                            dtag, source=f"battlelog:{tag}", depth=depth + 1, priority=60,
                        )
            await self._insert_battles(tag, battlelog, battlelog_r2_key)

        now_iso        = datetime.now(tz=timezone.utc).isoformat()
        classification = classify_player(new_profile=profile, old_profile=old_profile, battlelog=battlelog)
        arena          = profile.get("arena") or {}

        await self.db.upsert_player({
            "tag":                   tag,
            "name":                  profile.get("name"),
            "clan_tag":              clan_info.get("tag"),
            "clan_name":             clan_info.get("name"),
            "trophies":              profile.get("trophies"),
            "best_trophies":         profile.get("bestTrophies"),
            "exp_level":             profile.get("expLevel"),
            "arena_id":              arena.get("id"),
            "battle_count":          profile.get("battleCount"),
            "wins":                  profile.get("wins"),
            "losses":                profile.get("losses"),
            "three_crown_wins":      profile.get("threeCrownWins"),
            "donations":             profile.get("donations"),
            "donations_received":    profile.get("donationsReceived"),
            "last_seen_api":         profile.get("lastSeen"),
            "last_battle_time":      classification["last_battle_time"],
            "activity_status":       classification["activity_status"],
            "activity_score":        classification["activity_score"],
            "next_scan_at":          classification["next_scan_at"],
            "last_profile_scan_at":  now_iso,
            "last_battlelog_scan_at": now_iso if battlelog is not None else None,
            "discovery_depth":       depth,
        })
        await self.db.remove_player_from_queue(tag)
        console.print(f"[green]{tag} -> {classification['activity_status']} (score={classification['activity_score']})[/green]")

    async def _insert_battles(self, player_tag: str, battlelog: list, r2_key: Optional[str]) -> None:
        for battle in battlelog:
            team     = battle.get("team", [])
            opponent = battle.get("opponent", [])
            if not team or not opponent:
                continue
            p = team[0]
            o = opponent[0]
            pc = p.get("crowns", 0)
            oc = o.get("crowns", 0)
            result = "win" if pc > oc else ("loss" if pc < oc else "draw")
            gm = battle.get("gameMode") or {}
            await self.db.insert_battle_summary({
                "battle_id":          make_battle_id(battle, player_tag),
                "battle_time":        battle.get("battleTime"),
                "battle_type":        battle.get("type"),
                "game_mode":          gm.get("name"),
                "player_tag":         player_tag,
                "opponent_tag":       normalize_tag(o.get("tag", "")),
                "player_crowns":      pc,
                "opponent_crowns":    oc,
                "result":             result,
                "player_deck_hash":   deck_hash(p.get("cards", [])),
                "opponent_deck_hash": deck_hash(o.get("cards", [])),
                "raw_r2_key":         r2_key,
            })

    async def _scan_clan(self, clan_tag: str, depth: int) -> None:
        clan_tag = normalize_tag(clan_tag)
        safe     = safe_tag_for_path(clan_tag)
        console.print(f"[magenta]Scan clan {clan_tag} (depth={depth})[/magenta]")

        try:
            clan = await self._api.get_clan(clan_tag)
        except ClashAPIError:
            await self.db.increase_clan_attempt(clan_tag)
            return
        if clan is None:
            await self.db.remove_clan_from_queue(clan_tag)
            return

        if self.r2:
            try:
                self.r2.put_json_gz(self.r2.clan_key(safe), clan)
            except Exception:
                pass

        try:
            members = await self._api.get_clan_members(clan_tag)
        except ClashAPIError:
            members = None

        if members and self.r2:
            try:
                self.r2.put_json_gz(self.r2.clan_members_key(safe), members)
            except Exception:
                pass

        now_iso  = datetime.now(tz=timezone.utc).isoformat()
        location = clan.get("location") or {}
        await self.db.upsert_clan({
            "tag":                  clan_tag,
            "name":                 clan.get("name"),
            "location_id":          location.get("id"),
            "members":              clan.get("members"),
            "clan_score":           clan.get("clanScore"),
            "required_trophies":    clan.get("requiredTrophies"),
            "last_members_scan_at": now_iso,
            "next_members_scan_at": now_iso,
            "discovery_depth":      depth,
        })

        if members and depth + 1 <= config.CRAWL_MAX_DEPTH:
            for member in members:
                mtag = member.get("tag")
                if not mtag:
                    continue
                mtag    = normalize_tag(mtag)
                classif = classify_player(
                    new_profile={"lastSeen": member.get("lastSeen")},
                    clan_member=member,
                )
                await self.db.upsert_player({
                    "tag":             mtag,
                    "name":            member.get("name"),
                    "trophies":        member.get("trophies"),
                    "clan_tag":        clan_tag,
                    "clan_name":       clan.get("name"),
                    "donations":       member.get("donations"),
                    "last_seen_api":   member.get("lastSeen"),
                    "activity_status": classif["activity_status"],
                    "activity_score":  classif["activity_score"],
                    "next_scan_at":    classif["next_scan_at"],
                    "discovered_from": f"clan:{clan_tag}",
                    "discovery_depth": depth + 1,
                })
                prio = 70 if classif["activity_status"] in ("hot", "active") else 50
                await self.db.enqueue_player(
                    mtag, source=f"clan:{clan_tag}", depth=depth + 1, priority=prio
                )

        await self.db.remove_clan_from_queue(clan_tag)
        nb = len(members) if members else 0
        console.print(f"[green]Clan {clan_tag} OK — {nb} membres[/green]")

    async def _print_stats(self) -> None:
        t = Table(title="Crawl Stats", box=box.ROUNDED)
        t.add_column("Metrique", style="cyan")
        t.add_column("Valeur", style="bold white")
        t.add_row("Joueurs",       str(await self.db.count_players()))
        t.add_row("Clans",         str(await self.db.count_clans()))
        t.add_row("Batailles",     str(await self.db.count_battles()))
        t.add_row("Queue joueurs", str(await self.db.count_player_queue()))
        t.add_row("Queue clans",   str(await self.db.count_clan_queue()))
        console.print(t)
        bd = await self.db.activity_breakdown()
        if bd:
            t2 = Table(title="Activite", box=box.SIMPLE)
            t2.add_column("Status")
            t2.add_column("Count")
            for s, c in sorted(bd.items()):
                t2.add_row(s, str(c))
            console.print(t2)
