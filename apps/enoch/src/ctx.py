"""AppCtx definitions."""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot import EnochBot


class AppCtx(discord.ApplicationContext):
    bot: "EnochBot"


AppInteraction = AppCtx | discord.Interaction
