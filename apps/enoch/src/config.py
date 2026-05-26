"""Basic bot config."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip('/')
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    return url + '/'

BOT_TOKEN = os.environ.get("ENOCH_TOKEN", "")
API_KEY = os.environ.get("ENOCH_API_TOKEN", "")
DEBUG_GUILDS: Optional[list] = None
ADMIN_GUILD = int(os.environ["ADMIN_SERVER"])
SUPPORTER_GUILD = int(os.environ["SUPPORTER_GUILD"])
SUPPORTER_ROLE = int(os.environ["SUPPORTER_ROLE"])
STORYTELLER_ROLE: int | None = int(_st) if (_st := os.environ.get("STORYTELLER_ROLE")) else None
PROFILE_SITE = os.environ.get("PROFILE_SITE", "http://localhost:5173/")
SHOW_TEST_ROUTES = "SHOW_TEST_ROUTES" in os.environ
APP_SITE = os.environ.get("APP_SITE", "http://localhost:5173")
DASHBOARD_URL = _normalize_url(os.environ.get('DASHBOARD_URL', 'http://127.0.0.1:5001/'))
DASHBOARD_API_TOKEN = os.environ.get('DASHBOARD_API_TOKEN', '')
GUILD_CACHE_LOC = os.environ.get("GUILD_CACHE_LOC", "file::memory:?cache=shared")

if PROFILE_SITE[-1] != "/":
    PROFILE_SITE += "/"

if (_debug_guilds := os.getenv("DEBUG")) is not None:
    DEBUG_GUILDS = [int(g) for g in _debug_guilds.split(",")]

PROD = not DEBUG_GUILDS


def web_asset(path: str):
    """Returns the AWS URL for the given path."""
    base = "https://assets.Enoch.app/"
    if path[0] == "/":
        path = path[1:]
    return base + path
