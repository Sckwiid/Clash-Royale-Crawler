"""
clash_api.py — Client HTTP async Clash Royale v1.

- Rate limiting (RateLimiter token bucket)
- Retry backoff exponentiel (tenacity) sur 429 et 503
- 404 -> None sans crash
- 400 -> None (tag invalide)
- 403/500 -> ClashAPIError
"""
from __future__ import annotations
import asyncio
from typing import Any, Optional
from urllib.parse import quote
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from rich.console import Console
from src import config
from src.rate_limiter import RateLimiter

console = Console()

class RateLimitError(Exception):
    pass

class ServiceUnavailableError(Exception):
    pass

class ClashAPIError(Exception):
    pass

def _encode_tag(tag: str) -> str:
    return quote(tag.strip(), safe="")

class ClashRoyaleAPI:
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

    async def get_player(self, tag: str) -> Optional[dict[str, Any]]:
        return await self._request(f"/players/{_encode_tag(tag)}")

    async def get_player_battlelog(self, tag: str) -> Optional[list[dict]]:
        data = await self._request(f"/players/{_encode_tag(tag)}/battlelog")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        return data.get("items", [])

    async def get_clan(self, clan_tag: str) -> Optional[dict[str, Any]]:
        return await self._request(f"/clans/{_encode_tag(clan_tag)}")

    async def get_clan_members(self, clan_tag: str) -> Optional[list[dict]]:
        data = await self._request(f"/clans/{_encode_tag(clan_tag)}/members")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        return data.get("items", [])

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
                assert self._client is not None
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
                    console.print(f"[yellow]429 Rate limit — attente {wait_s}s[/yellow]")
                    await asyncio.sleep(wait_s)
                    raise RateLimitError(f"429 {url}")
                if code == 503:
                    console.print("[yellow]503 Maintenance — attente 60s[/yellow]")
                    await asyncio.sleep(60)
                    raise ServiceUnavailableError(f"503 {url}")
                if code == 403:
                    raise ClashAPIError(f"403 Forbidden: {url}")
                if code == 400:
                    return None
                raise ClashAPIError(f"HTTP {code}: {url}")

        return await _do()
