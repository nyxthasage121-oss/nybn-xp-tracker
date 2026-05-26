"""Primary Enoch import."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import EnochBot
from enoch import (
    character,
    experience,
    header,
    macros,
    misc,
    options,
    reference,
    roleplay,
    settings,
    specialties,
    stats,
    traits,
    vr,
)
from enoch.dice import d10, random
from enoch.roll import Roll
from enoch.settings import menu

__all__ = (
    "bot",
    "character",
    "d10",
    "menu",
    "experience",
    "header",
    "macros",
    "misc",
    "options",
    "random",
    "reference",
    "Roll",
    "roleplay",
    "settings",
    "specialties",
    "stats",
    "traits",
    "vr",
)

bot: "EnochBot"  # Assigned in bot.py
