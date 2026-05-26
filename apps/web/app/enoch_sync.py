"""enoch_sync.py — Mirror dashboard approvals onto Enoch character sheets.

Both apps share the same SQLite/Turso database, so Flask can write directly
to inconnu_characters without any HTTP hop.

All functions fail silently: if the character isn't found in Enoch (not yet
created there, or ENOCH_GUILD_ID not configured) they log a warning and return
False. The approval itself always succeeds regardless.
"""

import json
import logging
from datetime import UTC, datetime

from flask import current_app, session
from sqlalchemy import func

from .db import db, DbCharacter, DbInconnuChar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _guild_id() -> int:
    """Return the configured NYbN Discord guild ID, or 0 if unset."""
    return current_app.config.get('ENOCH_GUILD_ID', 0)


def _admin_id() -> int:
    """Return the approving staff member's Discord ID from session, or 0."""
    try:
        return int(session.get('discord_id') or 0)
    except (TypeError, ValueError):
        return 0


def _find_enoch_char(character_name: str) -> DbInconnuChar | None:
    """Find the inconnu_characters row for a Flask character.

    Matching order:
      1. guild + discord user ID + name  (precise — requires player to be linked)
      2. guild + name only               (fallback for unlinked characters)
    """
    guild = _guild_id()
    if not guild:
        logger.warning("enoch_sync: ENOCH_GUILD_ID not set — skipping sync")
        return None

    # Try precise match via linked Discord user
    flask_char = DbCharacter.query.filter(
        func.lower(DbCharacter.character_name) == character_name.lower()
    ).first()

    if flask_char and flask_char.player_discord:
        try:
            user_id = int(flask_char.player_discord)
            row = DbInconnuChar.query.filter_by(
                guild=guild, user=user_id
            ).filter(
                func.lower(DbInconnuChar.name) == character_name.lower()
            ).first()
            if row:
                return row
        except (TypeError, ValueError):
            pass

    # Fallback: name match within the guild
    return DbInconnuChar.query.filter_by(guild=guild).filter(
        func.lower(DbInconnuChar.name) == character_name.lower()
    ).first()


def _log_entry(event: str, amount: int, reason: str) -> dict:
    """Build an Enoch experience log entry."""
    return {
        "event": event,
        "amount": amount,
        "reason": reason,
        "admin": _admin_id(),
        "date": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def award_xp(character_name: str, amount: int, reason: str) -> bool:
    """Add XP to both unspent ('current') and lifetime ('total') on the Enoch sheet.

    Called after an XP claim is approved.
    """
    try:
        row = _find_enoch_char(character_name)
        if not row:
            logger.info("enoch_sync: no Enoch character found for '%s' — skipping award", character_name)
            return False

        exp = json.loads(row.experience or '{}')
        exp['current'] = exp.get('current', 0) + amount
        exp['total'] = exp.get('total', 0) + amount
        exp.setdefault('log', []).insert(0, _log_entry('Award', amount, reason))

        row.experience = json.dumps(exp)
        db.session.commit()
        logger.info("enoch_sync: awarded %d XP to '%s'", amount, character_name)
        return True

    except Exception:
        logger.exception("enoch_sync: failed to award XP to '%s'", character_name)
        db.session.rollback()
        return False


def deduct_xp(character_name: str, amount: int, reason: str) -> bool:
    """Deduct unspent XP ('current') from the Enoch sheet. Lifetime is unchanged.

    Called after an XP spend is approved.
    """
    try:
        row = _find_enoch_char(character_name)
        if not row:
            logger.info("enoch_sync: no Enoch character found for '%s' — skipping deduct", character_name)
            return False

        exp = json.loads(row.experience or '{}')
        exp['current'] = max(0, exp.get('current', 0) - amount)
        exp.setdefault('log', []).insert(0, _log_entry('Spend', -amount, reason))

        row.experience = json.dumps(exp)
        db.session.commit()
        logger.info("enoch_sync: deducted %d XP from '%s'", amount, character_name)
        return True

    except Exception:
        logger.exception("enoch_sync: failed to deduct XP from '%s'", character_name)
        db.session.rollback()
        return False


def update_trait(character_name: str, trait_name: str, new_rating: int) -> bool:
    """Set a trait's rating on the Enoch character sheet.

    Finds the trait case-insensitively. If the trait doesn't exist on the
    sheet yet (character hasn't added it in Enoch) this is a no-op — the XP
    deduction already happened via deduct_xp().
    """
    try:
        row = _find_enoch_char(character_name)
        if not row:
            logger.info(
                "enoch_sync: no Enoch character found for '%s' — skipping trait update",
                character_name,
            )
            return False

        traits = json.loads(row.traits or '[]')
        found = False
        for trait in traits:
            if trait.get('name', '').lower() == trait_name.lower():
                trait['rating'] = new_rating
                found = True
                break

        if not found:
            logger.info(
                "enoch_sync: trait '%s' not on '%s' sheet — skipping trait update",
                trait_name,
                character_name,
            )
            return False

        row.traits = json.dumps(traits)
        db.session.commit()
        logger.info(
            "enoch_sync: set %s → %s to %d dots", character_name, trait_name, new_rating
        )
        return True

    except Exception:
        logger.exception("enoch_sync: failed to update trait on '%s'", character_name)
        db.session.rollback()
        return False
