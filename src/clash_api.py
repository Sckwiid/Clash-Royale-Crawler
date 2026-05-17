"""
clash_api.py — Client HTTP async pour l API officielle Clash Royale v1.

Gestion:
  - Rate limiting (RateLimiter)
  - Retry avec backoff exponentiel (tenacity)
  - 404 -> None (pas un crash)
  - 429 -> respect Retry-After + backoff
  - 503 -> attente 60s + retry
  - 400/403/500 -> ClashAPIError
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from rich.console import Console

from src import config
from src.rate_limiter import RateLimiter

console = Console()


class RateLimitError(Exception):
    """429 - trop de requetes."""

class ServiceUnavailableError(Exception):
    """503 - maintenance API."""

class ClashAPIError(Exception):
    """Erreur API non retryable."""


def _encode_tag(tag: str) -> str:
    """Encode #GUUR8QP0 -> %23GUUR8QP0 pour l URL."""
    return quote(tag.strip(), safe="")


class ClashRoyaleAPI:
    """
    Client HTTP async Clash Royale.

    Usage:
        async with ClashRoyaleAPI() as api:
            player = await api.get_player("#GUUR8QP0")
            battlelog = await api.get_player_battlelog("#GUUR8QP0")
            clan = await api.get_clan("#XXXXX")
            members = await api.get_clan_members("#XXXXX")
    """

    def __init__(self) -> None:
        self._base_url = config.CLASH_API_BASE.rstrip("/")
        self._headers  = {
            "Authorization": f"Bearer {config.CLASH_API_TOKEN}",
            "Accept": "application/json",
        }
        self._limiter = RateLimiter(max_rps=config.MAX_RPS)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ClashRoyaleAPI":
        self._client = httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(30.0, connect=10.0),
            http2=True,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    # --- Endpoints publics

    async def get_player(self, tag: str) -> Optional[dict[str, Any]]:
        """Profil joueur. Retourne None si 404."""
        return await self._request(f"/players/{_encode_tag(tag)}")

    async def get_player_battlelog(self, tag: str) -> Optional[list[dict]]:
        """Battlelog joueur. Retourne None si 404."""
        data = await self._request(f"/players/{_encode_tag(tag)}/battlelog")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        return data.get("items", [])

    async def get_clan(self, clan_tag: str) -> Optional[dict[str, Any]]:
        """Infos d un clan. Retourne None si 404."""
        return await self._request(f"/clans/{_encode_tag(clan_tag)}")

    async def get_clan_members(self, clan_tag: str) -> Optional[list[dict]]:
        """Membres d un clan. Retourne None si 404."""
        data = await self._request(f"/clans/{_encode_tag(clan_tag)}/members")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        return data.get("items", [])

    # --- Methode interne avec retry

    async def _request(self, path: str) -> Optional[Any]:
        url = f"{self._base_url}{path}"

        @retry(
            retry=retry_if_exception_type((RateLimitError, ServiceUnavailableError)),
            wait=wait_exponential(multiplier=2, min=2, max=120),
            stop=stop_after_attempt(6),
            reraise=True,
        )
        async def _do() -> Optional[Any]:
            async with self._limiter:
                assert self._client is not None, "Utiliser async with ClashRoyaleAPI()"
                try:
                    resp = await self._client.get(url)
                except httpx.RequestError as exc:
                    console.print(f"[yellow]Erreur reseau {url}: {exc}[/yellow]")
                    raise ServiceUnavailableError(str(exc)) from exc

                code = resp.status_code

                if code == 200:
                    return resp.json()

                if code == 404:
                    return None

                if code == 429:
                    wait_s = int(resp.headers.get("Retry-After", "10"))
                    console.print(f"[yellow]429 Rate limit — attente {wait_s}s...[/yellow]")
                    await asyncio.sleep(wait_s)
                    raise RateLimitError(f"429 {url}")

                if code == 503:
                    console.print("[yellow]503 Maintenance API — attente 60s...[/yellow]")
                    await asyncio.sleep(60)
                    raise ServiceUnavailableError(f"503 {url}")

                if code == 403:
                    console.print(f"[red]403 Interdit: {url}[/red]")
                    raise ClashAPIError(f"403 Forbidden: {url}")

                if code == 400:
                    console.print(f"[yellow]400 Mauvais tag: {url}[/yellow]")
                    return None  # Tag invalide, on ignore

                console.print(f"[red]HTTP {code}: {url}[/red]")
                raise ClashAPIError(f"HTTP {code}: {url}")

        return await _do()
