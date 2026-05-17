"""
r2_storage.py — Stockage JSON compresse (gzip) dans Cloudflare R2 via boto3.

Structure des cles :
  raw/players/{safe_tag}/{YYYY-MM-DD}/{timestamp}.json.gz
  raw/battlelogs/{safe_tag}/{YYYY-MM-DD}/{timestamp}.json.gz
  raw/clans/{safe_tag}/{YYYY-MM-DD}/{timestamp}.json.gz
  raw/clan_members/{safe_tag}/{YYYY-MM-DD}/{timestamp}.json.gz
"""

from __future__ import annotations

import gzip
from datetime import datetime, timezone
from typing import Any

import boto3
import orjson
from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

from src import config

console = Console()


class R2Storage:
    """Client Cloudflare R2 pour stocker les raw JSON compresses."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=config.R2_ENDPOINT_URL,
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self._bucket = config.R2_BUCKET

    def put_json_gz(self, key: str, data: Any) -> str:
        """Serialise en JSON, compresse gzip, uploade dans R2. Retourne la cle."""
        raw_json   = orjson.dumps(data)
        compressed = gzip.compress(raw_json, compresslevel=6)

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=compressed,
                ContentType="application/json",
                ContentEncoding="gzip",
            )
            console.print(f"[dim cyan]R2 stored: {key}[/dim cyan]")
        except (BotoCoreError, ClientError) as exc:
            console.print(f"[red]R2 upload FAILED ({key}): {exc}[/red]")
            raise

        return key

    # --- Helpers construction cles

    @staticmethod
    def _date_prefix() -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _ts() -> str:
        return str(int(datetime.now(tz=timezone.utc).timestamp()))

    def player_key(self, safe_tag: str) -> str:
        return f"raw/players/{safe_tag}/{self._date_prefix()}/{self._ts()}.json.gz"

    def battlelog_key(self, safe_tag: str) -> str:
        return f"raw/battlelogs/{safe_tag}/{self._date_prefix()}/{self._ts()}.json.gz"

    def clan_key(self, safe_tag: str) -> str:
        return f"raw/clans/{safe_tag}/{self._date_prefix()}/{self._ts()}.json.gz"

    def clan_members_key(self, safe_tag: str) -> str:
        return f"raw/clan_members/{safe_tag}/{self._date_prefix()}/{self._ts()}.json.gz"
