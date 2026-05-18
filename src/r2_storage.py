"""
r2_storage.py — Stockage JSON gzip dans Cloudflare R2 (S3-compatible).

Cles:
  raw/players/{tag}/{YYYY-MM-DD}/{ts}.json.gz
  raw/battlelogs/{tag}/{YYYY-MM-DD}/{ts}.json.gz
  raw/clans/{tag}/{YYYY-MM-DD}/{ts}.json.gz
  raw/clan_members/{tag}/{YYYY-MM-DD}/{ts}.json.gz
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
        compressed = gzip.compress(orjson.dumps(data), compresslevel=6)
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=compressed,
                ContentType="application/json", ContentEncoding="gzip",
            )
            console.print(f"[dim cyan]R2: {key}[/dim cyan]")
        except (BotoCoreError, ClientError) as exc:
            console.print(f"[red]R2 FAILED ({key}): {exc}[/red]")
            raise
        return key

    @staticmethod
    def _date() -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _ts() -> str:
        return str(int(datetime.now(tz=timezone.utc).timestamp()))

    def player_key(self, t: str) -> str:
        return f"raw/players/{t}/{self._date()}/{self._ts()}.json.gz"

    def battlelog_key(self, t: str) -> str:
        return f"raw/battlelogs/{t}/{self._date()}/{self._ts()}.json.gz"

    def clan_key(self, t: str) -> str:
        return f"raw/clans/{t}/{self._date()}/{self._ts()}.json.gz"

    def clan_members_key(self, t: str) -> str:
        return f"raw/clan_members/{t}/{self._date()}/{self._ts()}.json.gz"
