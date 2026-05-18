"""
utils.py — Utilitaires divers.
"""
from __future__ import annotations
import asyncio
from typing import Any, Callable

async def run_with_semaphore(
    semaphore: asyncio.Semaphore,
    coro_func: Callable,
    *args: Any,
    **kwargs: Any,
) -> Any:
    async with semaphore:
        return await coro_func(*args, **kwargs)
