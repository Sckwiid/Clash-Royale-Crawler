"""
classifier.py — Classifie les joueurs par niveau d'activite.

Scoring:
  lastSeen <= 24h  : +100  |  battleTime <= 24h  : +90
  lastSeen <= 7j   : +70   |  battleTime <= 7j   : +60
  lastSeen <= 30j  : +30   |  battleTime <= 30j  : +25
  battleCount++    : +80   |  trophies change    : +25
  donations change : +20

Status: hot(>=100) / active(>=60) / warm(>=25) / cold(>0) / unknown(0)
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from src.normalize import parse_cr_time

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)

def classify_player(
    new_profile: dict[str, Any],
    old_profile: Optional[dict[str, Any]] = None,
    battlelog: Optional[list[dict[str, Any]]] = None,
    clan_member: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    score = 0
    now   = _now()

    last_seen_raw = new_profile.get("lastSeen") or (
        clan_member.get("lastSeen") if clan_member else None
    )
    last_seen_dt = parse_cr_time(last_seen_raw)
    if last_seen_dt:
        delta = now - last_seen_dt
        if   delta <= timedelta(hours=24): score += 100
        elif delta <= timedelta(days=7):   score += 70
        elif delta <= timedelta(days=30):  score += 30

    last_battle_time_raw: Optional[str] = None
    if battlelog:
        times = [b.get("battleTime", "") for b in battlelog if b.get("battleTime")]
        last_battle_time_raw = max(times) if times else None

    last_battle_dt = parse_cr_time(last_battle_time_raw)
    if last_battle_dt:
        delta = now - last_battle_dt
        if   delta <= timedelta(hours=24): score += 90
        elif delta <= timedelta(days=7):   score += 60
        elif delta <= timedelta(days=30):  score += 25

    if old_profile:
        if (new_profile.get("battleCount") or 0) > (old_profile.get("battle_count") or 0):
            score += 80
        if (new_profile.get("trophies") or 0) != (old_profile.get("trophies") or 0):
            score += 25
        if (new_profile.get("donations") or 0) != (old_profile.get("donations") or 0):
            score += 20

    if   score >= 100: status = "hot"
    elif score >= 60:  status = "active"
    elif score >= 25:  status = "warm"
    elif score > 0:    status = "cold"
    else:              status = "unknown"

    return {
        "activity_score":   score,
        "activity_status":  status,
        "next_scan_at":     compute_next_scan_at(status),
        "last_battle_time": last_battle_time_raw,
    }

def compute_next_scan_at(status: str) -> str:
    now = _now()
    deltas = {
        "hot":     timedelta(minutes=30),
        "active":  timedelta(hours=3),
        "warm":    timedelta(hours=24),
        "cold":    timedelta(days=7),
        "unknown": timedelta(hours=24),
    }
    return (now + deltas.get(status, timedelta(hours=24))).isoformat()
