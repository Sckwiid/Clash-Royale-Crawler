"""
config.py — Chargement et validation de la configuration depuis .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Variable d'environnement obligatoire manquante : {key}\n"
            f"Verifiez votre fichier .env (voir .env.example)."
        )
    return value

def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

# Clash Royale API
CLASH_API_TOKEN: str  = _require("CLASH_API_TOKEN")
CLASH_API_BASE: str   = _optional("CLASH_API_BASE", "https://api.clashroyale.com/v1")

# Turso
TURSO_DATABASE_URL: str = _require("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN: str   = _require("TURSO_AUTH_TOKEN")

# Cloudflare R2
R2_BUCKET: str             = _optional("R2_BUCKET", "clash-royale-raw")
R2_ENDPOINT_URL: str       = _require("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID: str      = _require("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY: str  = _require("R2_SECRET_ACCESS_KEY")

# Crawler
SEED_PLAYER_TAG: str         = _optional("SEED_PLAYER_TAG", "#GUUR8QP0")
MAX_RPS: float               = float(_optional("MAX_RPS", "5"))
MAX_CONCURRENT_REQUESTS: int = int(_optional("MAX_CONCURRENT_REQUESTS", "5"))
CRAWL_MAX_DEPTH: int         = int(_optional("CRAWL_MAX_DEPTH", "4"))
CRAWL_MAX_PLAYERS: int       = int(_optional("CRAWL_MAX_PLAYERS", "100000"))
STORE_RAW_JSON: bool         = _optional("STORE_RAW_JSON", "true").lower() == "true"
