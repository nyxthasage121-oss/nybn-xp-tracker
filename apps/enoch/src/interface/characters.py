"""interface/characters.py - Character management Cog."""

from typing import TYPE_CHECKING

import discord
from discord import option
from discord.commands import OptionChoice, SlashCommandGroup
from discord.ext import commands

import enoch
import ui
from ctx import AppCtx
from enoch.character.approve import approve as _approve_character
from enoch.options import char_option, player_option
from utils import decorators, not_on_lockdown
from utils.permissions import require_admin_or_storyteller, require_helper_or_above
from utils.text import strtobool

if TYPE_CHECKING:
    from bot import EnochBot


async def _spc_options(ctx):
    """Determine whether the user can make an SPC."""
    if ctx.interaction.user.guild_permissions.administrator:
        return [OptionChoice("No", "0"), OptionChoice("Yes", "1")]
    return [OptionChoice("No", "0")]


class Characters(commands.Cog, name="Character Management"):
    """Character management commands."""

    _TEMPLATES = [
        OptionChoice("Vampire", "vampire"),
        OptionChoice("Ghoul", "ghoul"),
        OptionChoice("Mortal", "mortal"),
        OptionChoice("Thin-Blood", "thinblood"),
    ]

    def __init__(self, bot: "EnochBot"):
        super().__init__()
        self.bot = bot

    @commands.user_command(name="Stats", contexts={discord.InteractionContextType.guild})
    async def user_characters(self, ctx, member):
        """Display the user's character(s)."""
        await Enoch.character.display_requested(ctx, None, player=member, ephemeral=True)

    character = SlashCommandGroup(
        "character",
        "Character commands.",
        contexts={discord.InteractionContextType.guild},
    )

    @character.command(name="wizard", contexts={discord.InteractionContextType.guild})
    @not_on_lockdown()
    @option("spc", description="(Admin only) Make an SPC", autocomplete=_spc_options, default="0")
    async def character_wizard(self, ctx: AppCtx, spc: str):
        """Start a character creation wizard."""
        try:
            make_spc = bool(strtobool(spc))
            await Enoch.character.create.launch_wizard(ctx, make_spc)
        except ValueError:
            await ui.embeds.error(ctx, f'Invalid value for `spc`: "{spc}".')

    _CLANS = [
        "Banu Haqim", "Brujah", "Caitiff", "Gangrel", "Hecata",
        "Lasombra", "Malkavian", "Ministry", "Nosferatu", "Ravnos",
        "Salubri", "Toreador", "Tremere", "Tzimisce", "Ventrue", "Thin-Blood",
    ]
    _SECTS = ["Camarilla", "Anarch", "Hecata", "Autarkis", "Sabbat"]
    _AGES  = ["Fledgling", "Neonate", "Ancilla", "Elder"]

    @character.command(name="approve")
    @require_helper_or_above()
    @option("player",         description="The player being approved",    type=discord.Member)
    @option("name",           description="Character name")
    @option("clan",           description="Vampire clan",                 choices=[OptionChoice(c, c) for c in _CLANS])
    @option("sect",           description="Sect or faction",              choices=[OptionChoice(s, s) for s in _SECTS])
    @option("age_category",   description="Age category",                 choices=[OptionChoice(a, a) for a in _AGES])
    @option("cubby",          description="Player's cubby channel (defaults to current channel)", type=discord.TextChannel, required=False, default=None)
    @option("creation_xp",    description="Starting XP (default 0)",      type=int, required=False, default=0)
    async def character_approve(
        self,
        ctx: AppCtx,
        player: discord.Member,
        name: str,
        clan: str,
        sect: str,
        age_category: str,
        cubby: discord.TextChannel | None,
        creation_xp: int,
    ):
        """Approve a character: register in dashboard, assign roles, notify player."""
        await _approve_character(
            ctx=ctx,
            player=player,
            character_name=name,
            clan=clan,
            sect=sect,
            age_category=age_category,
            cubby=cubby,
            creation_xp=creation_xp,
        )

    @character.command(name="create")
    @not_on_lockdown()
    async def character_create(self, ctx: AppCtx):
        """[DEPRECATED] Use /character wizard instead!"""
        wizard = self.bot.cmd_mention("character wizard")
        await ctx.respond(f"This command has been removed! Use {wizard} instead.", ephemeral=True)

    @commands.slash_command(name="spc", contexts={discord.InteractionContextType.guild})
    @commands.has_permissions(administrator=True)
    async def spc_create(self, ctx: AppCtx):
        """[DEPRECATED] Use /character wizard instead!"""
        wizard = self.bot.cmd_mention("character wizard")
        await ctx.respond(f"This command has been removed! Use {wizard} instead.", ephemeral=True)

    @character.command(name="display")
    @char_option("The character to display")
    @player_option()
    async def character_display(
        self,
        ctx: AppCtx,
        character: str,
        player: discord.Member,
    ):
        """Display a character's trackers."""
        await Enoch.character.display_requested(ctx, character, player=player)

    @character.command(name="update")
    @option("parameters", description="KEY=VALUE parameters (see /help characters)")
    @char_option("The character to update")
    @player_option()
    async def character_update(
        self,
        ctx: AppCtx,
        parameters: str,
        character: str,
        player: discord.Member,
    ):
        """Update a character's parameters but not the traits."""
        await Enoch.character.update(ctx, parameters, character, player=player)

    @character.command(name="adjust")
    @option("new_name", description="The character's new name", required=False)
    @option(
        "health",
        description="The new Health rating",
        choices=Enoch.options.ratings(4, 20),
        required=False,
    )
    @option(
        "willpower",
        description="The new Willpower rating",
        choices=Enoch.options.ratings(3, 20),
        required=False,
    )
    @option(
        "humanity",
        description="The new Humanity rating",
        choices=Enoch.options.ratings(0, 10),
        required=False,
    )
    @option("template", description="The character's new type", choices=_TEMPLATES, required=False)
    @option("sup_hp", description="Superficial Health (Tip: Use +X/-X)", required=False)
    @option("agg_hp", description="Aggravated Health (Tip: Use +X/-X)", required=False)
    @option("sup_wp", description="Superficial Willpower (Tip: Use +X/-X)", required=False)
    @option("agg_wp", description="Aggravated Willpower (Tip: Use +X/-X)", required=False)
    @option("stains", description="Stains (Tip: Use +X/-X)", required=False)
    @option("unspent_xp", description="Unspent XP (Tip: Use +X/-X)", required=False)
    @option("lifetime_xp", description="Lifetime XP (Tip: Use +X/-X)", required=False)
    @option("hunger", description="Adjust Hunger", required=False)
    @option("potency", description="Adjust Blood Potency", required=False)
    @char_option("The character to adjust")
    @player_option()
    async def adjust_character(
        self,
        ctx,
        new_name: str,
        health: int,
        willpower: int,
        humanity: int,
        template: str,
        sup_hp: str,
        agg_hp: str,
        sup_wp: str,
        agg_wp: str,
        stains: str,
        unspent_xp: str,
        lifetime_xp: str,
        hunger: str,
        potency: str,
        character: str,
        player: discord.Member,
    ):
        """Adjust a character's trackers. For skills and attributes, see /traits help."""

        # We will construct an update string and call the old-style parser
        parameters = []

        if new_name is not None:
            new_name = " ".join(new_name.split())  # Normalize the name first
            parameters.append(f"name={new_name}")

        if health is not None:
            parameters.append(f"health={health}")

        if willpower is not None:
            parameters.append(f"willpower={willpower}")

        if humanity is not None:
            parameters.append(f"humanity={humanity}")

        if template is not None:
            parameters.append(f"template={template}")

        # The rest of these are adjustments, but they must be able to convert into an int
        try:
            if _check_number("sup_hp", sup_hp):
                parameters.append(f"sh={sup_hp}")

            if _check_number("agg_hp", agg_hp):
                parameters.append(f"ah={agg_hp}")

            if _check_number("sup_wp", sup_wp):
                parameters.append(f"sw={sup_wp}")

            if _check_number("agg_wp", agg_wp):
                parameters.append(f"aw={agg_wp}")

            if _check_number("stains", stains):
                parameters.append(f"stains={stains}")

            if _check_number("lifetime_xp", lifetime_xp):
                parameters.append(f"lxp={lifetime_xp}")

            if _check_number("unspent_xp", unspent_xp):
                parameters.append(f"uxp={unspent_xp}")

            if _check_number("hunger", hunger):
                parameters.append(f"hunger={hunger}")

            if _check_number("potency", potency):
                parameters.append(f"potency={potency}")

            # Combine the parameters and send them off to the updater
            parameters = " ".join(parameters)
            await Enoch.character.update(ctx, parameters, character, player=player)

        except ValueError as err:
            await ctx.respond(err, ephemeral=True)

    @character.command(name="delete")
    @not_on_lockdown()
    @char_option("The character to delete", required=True)
    async def character_delete(
        self,
        ctx: AppCtx,
        character: str,
    ):
        """Delete a character."""
        await Enoch.character.delete(ctx, character)

    @character.command(name="profile")
    @player_option(description="The character's owner (does not work with EDIT)")
    @char_option("The character to show")
    @char_option("The character whose profile to edit", param="edit")
    async def character_profile(
        self,
        ctx: AppCtx,
        player: discord.Member,
        character: str,
        edit: str,
    ):
        """Show or edit a character profile."""
        if edit:
            await Enoch.character.edit_biography(ctx, edit)
        else:
            await Enoch.character.show_biography(ctx, character, player=player)

    @commands.user_command(name="Profile", contexts={discord.InteractionContextType.guild})
    async def character_bio_context(self, ctx, member):
        """View a character's profile."""
        await Enoch.character.show_biography(ctx, None, player=member, ephemeral=True)

    # Convictions

    @character.command(name="convictions")
    @char_option("The character to show")
    @player_option(description="The character's owner (does not work with EDIT)")
    @char_option("The character whose convictions to edit", param="edit")
    async def character_convictions(
        self,
        ctx: AppCtx,
        character: str,
        player: discord.Member,
        edit: str,
    ):
        """Show a character's Convictions."""
        if not edit:
            await Enoch.character.convictions_show(ctx, character, player=player, ephemeral=False)
        else:
            await Enoch.character.convictions_set(ctx, edit)

    @commands.user_command(name="Convictions", contexts={discord.InteractionContextType.guild})
    async def character_convictions_context(self, ctx, member):
        """Show a character's Convictions."""
        await Enoch.character.convictions_show(ctx, None, player=member, ephemeral=True)

    # Premium

    @character.command(name="images")
    @Enoch.options.char_option("The character to display")
    @Enoch.options.player_option(description="The character's owner")
    @option(
        "controls",
        description="Who can press the pager buttons? (Default everyone)",
        choices=["Everyone", "Only me"],
        default="Everyone",
    )
    async def show_character_images(
        self,
        ctx: AppCtx,
        character: str,
        player: discord.Member,
        controls: str,
    ):
        """Display a character's images."""
        invoker_controls = controls == "Only me"
        await Enoch.character.images.display(ctx, character, invoker_controls, player=player)

    images = character.create_subgroup("image", "Character image commands")

    @images.command(name="upload")
    @decorators.premium()
    @option("image", description="The image file to upload")
    @char_option()
    async def upload_image(
        self,
        ctx: AppCtx,
        image: discord.Attachment,
        character: str,
    ):
        """Upload an image for your character's profile."""
        await Enoch.character.images.upload(ctx, character, image)


def _check_number(label, value):
    """Check whether a given value is a number. Raise a ValueError if not."""
    if value is None:
        return False

    try:
        int(value)  # The user might have given a +/-, so we can't use .isdigit()
        return True
    except ValueError:
        raise ValueError(f"`{label}` must be a number (with or without `+/-`.") from ValueError


def setup(bot):
    """Add the cog to the bot."""
    bot.add_cog(Characters(bot))
