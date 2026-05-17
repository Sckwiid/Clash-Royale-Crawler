"""
normalize.py — Normalisation des donnees Clash Royale.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Optional


def normalize_tag(tag: str) -> str:
    """Normalise un tag : ajoute #, majuscules, trim."""
    tag = tag.strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


def safe_tag_for_path(tag: str) -> str:
    """Convertit #GUUR8QP0 en GUUR8QP0 pour les chemins R2."""
    return tag.lstrip("#").upper()


_CR_TIME_PATTERN = re.compile(
    r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(?:\.\d+)?Z$"
)


def parse_cr_time(cr_time: Optional[str]) -> Optional[datetime]:
    """Convertit le format CR (20240517T143025.000Z) en datetime UTC."""
    if not cr_time:
        return None
    m = _CR_TIME_PATTERN.match(cr_time)
    if not m:
        return None
    try:
        return datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)), int(m.group(6)),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def deck_hash(cards: list[dict[str, Any]]) -> str:
    """Hash stable d un deck a partir des IDs de cartes tries."""
    ids = sorted(str(c.get("id", "")) for c in cards if c.get("id"))
    return hashlib.md5("|".join(ids).encode()).hexdigest()


def make_battle_id(battle_entry: dict[str, Any], player_tag: str) -> str:
    """ID stable pour une bataille : battleTime + tags + decks."""
    battle_time = battle_entry.get("battleTime", "")
    team     = battle_entry.get("team", [])
    opponent = battle_entry.get("opponent", [])
    team_tags = sorted(p.get("tag", "") for p in team)
    opp_tags  = sorted(p.get("tag", "") for p in opponent)
    raw = f"{battle_time}|{player_tag}|{'_'.join(team_tags)}|{'_'.join(opp_tags)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def extract_tags_from_battlelog(battlelog: list[dict[str, Any]]) -> set[str]:
    """Extrait tous les tags de joueurs (team + opponent) d un battlelog."""
    tags: set[str] = set()
    for battle in battlelog:
        for side in ("team", "opponent"):
            for player in battle.get(side, []):
                tag = player.get("tag")
                if tag and isinstance(tag, str):
                    tags.add(normalize_tag(tag))
    return tags


def extract_last_battle_time(battlelog: list[dict[str, Any]]) -> Optional[str]:
    """Retourne le battleTime le plus recent du battlelog."""
    times = [b.get("battleTime", "") for b in battlelog if b.get("battleTime")]
    return max(times) if times else None
