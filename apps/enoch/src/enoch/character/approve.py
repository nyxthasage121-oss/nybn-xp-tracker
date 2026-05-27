"""enoch/character/approve.py — Staff character approval command logic."""

import discord
from loguru import logger

from services.dashboard import DashboardError, create_character

# ---------------------------------------------------------------------------
# Approval message template — NYbN character approval message.
# Available variables: {character_name}, {player_mention}, {clan}, {sect}
# ---------------------------------------------------------------------------
APPROVAL_MESSAGE = """\
{player_mention}

<:Complete:1230869334843330600> Attributes
<:Complete:1230869334843330600> Skills
<:Complete:1230869334843330600> Predator Type
<:Complete:1230869334843330600> Disciplines
<:Complete:1230869334843330600> Character Thresholds (Health, Humanity, Willpower and Blood Potency)
<:Complete:1230869334843330600> Merits/Flaws
<:Complete:1230869334843330600> Convictions & Tenets
<:Complete:1230869334843330600> XP Spend
<:Complete:1230869334843330600> Backstory

# {character_name} — Character Approved

**Welcome to NYBN!**

If you want you can create your character profile in: https://discord.com/channels/1201856861108707348/1202154508239503360

And you can put your character in Enoch now in here: https://discord.com/channels/1201856861108707348/1201861978230886430

There is alot of helpful information about house rules and server ettiquette here https://discord.com/channels/1201856861108707348/1238725819702968380 and here https://discord.com/channels/1201856861108707348/1238640428731990086

After that you can look for RP scenes here: https://discord.com/channels/1201856861108707348/1201861096177422356

You can also search for rumors here: https://discord.com/channels/1201856861108707348/1201861330483814463

If you need help with anything just let me know!
"""


async def approve(
    ctx: discord.ApplicationContext,
    player: discord.Member,
    character_name: str,
    clan: str,
    sect: str,
    age_category: str,
    cubby: discord.TextChannel | None,
    creation_xp: int,
):
    """Approve a character: create it in the dashboard, assign roles, notify player."""
    await ctx.defer(ephemeral=True)

    # Default to the channel the command was run in (usually the player's cubby)
    cubby = cubby or ctx.channel

    # 1. Create in dashboard -----------------------------------------------
    try:
        await create_character(
            character_name=character_name,
            discord_id=player.id,
            discord_name=player.display_name,
            clan=clan,
            sect=sect,
            age_category=age_category,
            creation_xp=creation_xp,
            cubby_channel_id=cubby.id if cubby else None,
            approver=ctx.user.display_name,
        )
    except DashboardError as exc:
        await ctx.respond(f"❌ Dashboard error: {exc}", ephemeral=True)
        return

    # 2. Assign roles --------------------------------------------------------
    role_results: list[str] = []
    for role_name in (clan, sect):
        if not role_name:
            continue
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            try:
                await player.add_roles(role, reason=f"Character approved: {character_name}")
                role_results.append(f"✅ {role_name}")
            except discord.Forbidden:
                role_results.append(f"⚠️ {role_name} (no permission)")
        else:
            role_results.append(f"⚠️ {role_name} (role not found)")

    # 3. Post approval message -----------------------------------------------
    message = APPROVAL_MESSAGE.format(
        player_mention=player.mention,
        character_name=character_name,
        clan=clan,
        sect=sect,
    )

    posted_to = None
    if cubby:
        try:
            await cubby.send(message)
            posted_to = cubby.mention
        except discord.Forbidden:
            pass

    if not posted_to:
        try:
            await player.send(message)
            posted_to = "DM"
        except discord.Forbidden:
            posted_to = "nowhere (no cubby or DM access)"

    # 4. Confirm to staff ---------------------------------------------------
    roles_summary = ", ".join(role_results) if role_results else "none assigned"
    await ctx.respond(
        f"✅ **{character_name}** approved.\n"
        f"Roles: {roles_summary}\n"
        f"Message sent to: {posted_to}",
        ephemeral=True,
    )

    logger.info(
        "Character approved: {} (player={}, clan={}, sect={}) by {}",
        character_name, player.display_name, clan, sect, ctx.user.display_name,
    )
