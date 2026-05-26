"""services/dashboard.py — Async HTTP client for the Flask dashboard API."""

import json

import aiohttp
import async_timeout
from loguru import logger

from config import DASHBOARD_API_TOKEN, DASHBOARD_URL

_HEADER = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DASHBOARD_API_TOKEN}",
}


class DashboardError(Exception):
    """Raised when the dashboard API returns an error."""


async def create_character(
    *,
    character_name: str,
    discord_id: int,
    discord_name: str,
    clan: str,
    sect: str,
    age_category: str,
    creation_xp: int = 0,
    cubby_channel_id: int | None = None,
    approver: str = '',
) -> dict:
    """POST /api/characters — create an approved character in the dashboard.

    Returns the parsed JSON response on success.
    Raises DashboardError on HTTP error or timeout.
    """
    if not DASHBOARD_API_TOKEN:
        raise DashboardError("DASHBOARD_API_TOKEN is not configured")

    payload = {
        "character_name": character_name,
        "discord_id": str(discord_id),
        "discord_name": discord_name,
        "clan": clan,
        "sect": sect,
        "age_category": age_category,
        "creation_xp": creation_xp,
        "approver": approver,
    }
    if cubby_channel_id:
        payload["cubby_channel_id"] = str(cubby_channel_id)

    url = DASHBOARD_URL + "api/characters"
    try:
        async with async_timeout.timeout(15):
            async with aiohttp.ClientSession(headers=_HEADER) as session:
                async with session.post(url, data=json.dumps(payload)) as resp:
                    body = await resp.json()
                    if not resp.ok:
                        raise DashboardError(body.get("error", f"HTTP {resp.status}"))
                    return body
    except DashboardError:
        raise
    except Exception as exc:
        raise DashboardError(str(exc)) from exc
