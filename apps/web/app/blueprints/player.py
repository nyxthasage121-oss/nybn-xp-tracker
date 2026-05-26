"""Player-facing routes. Requires Discord authentication."""

from flask import (
    Blueprint, render_template, request, abort, flash, redirect, url_for,
    session,
)
from app import db_service, sheets_sync
from app.auth import (
    require_login, require_character_owner, is_staff as check_is_staff,
    get_player_discord_id,
)
from app.models import SPEND_CATEGORIES
from app.game_calendar import get_calendar

bp = Blueprint('player', __name__)


@bp.route('/')
@require_login
def my_characters():
    """Player landing page showing their linked characters."""
    discord_id = get_player_discord_id()
    my_chars = db_service.get_characters_by_discord_id(discord_id)

    # Fetch open periods for the banner
    all_periods = db_service.get_all_periods()
    open_periods = [p for p in all_periods if p.submissions_open and p.active]
    open_periods.sort(key=lambda p: p.night_number, reverse=True)

    calendar = get_calendar()

    # Coterie membership for each of the player's characters
    coteries = {
        char.character_name: db_service.get_coterie_for_character(char.character_name)
        for char in my_chars
    }

    # Staff also see a full character search
    if check_is_staff():
        all_characters = db_service.get_active_characters()
        all_characters.sort(key=lambda c: c.character_name.lower())
        return render_template(
            'player/my_characters.html',
            my_characters=my_chars,
            all_characters=all_characters,
            show_all=True,
            open_periods=open_periods,
            calendar=calendar,
            coteries=coteries,
        )

    if not my_chars:
        # No linked characters — show linking flow
        return redirect(url_for('player.link_character'))

    # Show character list with option to link more
    return render_template(
        'player/my_characters.html',
        my_characters=my_chars,
        all_characters=None,
        show_all=False,
        open_periods=open_periods,
        calendar=calendar,
        coteries=coteries,
    )


@bp.route('/link', methods=['GET', 'POST'])
@require_login
def link_character():
    """Let a player link their Discord account to a character."""
    discord_id = get_player_discord_id()
    discord_name = session.get('discord_name', '')

    # Check if they already have characters
    existing = db_service.get_characters_by_discord_id(discord_id)

    if request.method == 'GET':
        unlinked = db_service.get_unlinked_characters()
        unlinked.sort(key=lambda c: c.character_name.lower())
        return render_template(
            'player/link_character.html',
            unlinked_characters=unlinked,
            existing_characters=existing,
        )

    # POST: process linking
    character_name = request.form.get('character_name', '').strip()
    if not character_name:
        flash('Please select a character.', 'danger')
        return redirect(url_for('player.link_character'))

    char = db_service.get_character(character_name)
    if not char:
        flash('Character not found.', 'danger')
        return redirect(url_for('player.link_character'))

    if char.player_discord and char.player_discord != discord_id:
        flash('This character is already linked to another player.', 'danger')
        return redirect(url_for('player.link_character'))

    db_service.link_character_to_discord(character_name, discord_id, discord_name)
    db_service.log_action(
        staff_user=f'player:{discord_name}',
        action_type='player_link_character',
        target=character_name,
        details=f'Player self-linked Discord ID {discord_id} ({discord_name})',
    )
    if sheets_sync:
        sheets_sync.sync_log_action(
            staff_user=f'player:{discord_name}',
            action_type='player_link_character',
            target=character_name,
            details=f'Player self-linked Discord ID {discord_id} ({discord_name})',
        )
    flash(f'Successfully linked {character_name} to your Discord account.', 'success')
    return redirect(url_for('player.character', name=character_name))


@bp.route('/<name>')
@require_character_owner
def character(name):
    """Character XP summary with submission forms."""
    char = db_service.get_character(name)
    if not char:
        abort(404)

    claims = db_service.get_claims_for_character(name)
    spends = db_service.get_spends_for_character(name)

    # Only show approved data to players
    approved_claims = [
        c for c in claims if c.status.lower() == 'approved'
    ]
    approved_spends = [
        s for s in spends if s.status.lower() == 'approved'
    ]
    pending_claims = [
        c for c in claims if c.status.lower() == 'pending'
    ]
    pending_spends = [
        s for s in spends if s.status.lower() == 'pending'
    ]

    ledger = db_service.get_ledger_for_character(name)

    # Compute XP totals (includes ledger)
    xp = db_service.get_xp_totals(name)

    # Open periods for claim form dropdown
    all_periods = db_service.get_all_periods()
    open_periods = [p for p in all_periods if p.submissions_open and p.active]
    open_periods.sort(key=lambda p: p.night_number, reverse=True)

    # Periods this character has already claimed (non-denied)
    claimed_periods = {
        c.play_period for c in claims
        if c.status.lower() != 'denied'
    }

    criteria = db_service.get_active_criteria()

    return render_template(
        'player/character.html',
        char=char,
        earned_xp=xp['earned_xp'],
        total_xp=xp['total_xp'],
        total_spends=xp['total_spends'] + xp['ledger_spent'],
        available_xp=xp['available_xp'],
        xp_to_cap=xp.get('xp_to_cap', 350),
        cap_reached=xp.get('cap_reached', False),
        approved_claims=approved_claims,
        approved_spends=approved_spends,
        pending_claims_count=len(pending_claims),
        pending_spends_count=len(pending_spends),
        ledger=ledger,
        open_periods=open_periods,
        claimed_periods=claimed_periods,
        criteria=criteria,
        spend_categories=SPEND_CATEGORIES,
    )


@bp.route('/<name>/claim', methods=['POST'])
@require_character_owner
def submit_claim(name):
    """Submit an XP claim for a play period."""
    char = db_service.get_character(name)
    if not char or not char.active:
        abort(404)

    play_period = request.form.get('play_period', '').strip()
    if not play_period:
        flash('Please select a play period.', 'danger')
        return redirect(url_for('player.character', name=name))

    # Validate period exists and is open
    all_periods = db_service.get_all_periods()
    period = next((p for p in all_periods if p.period_label == play_period), None)
    if not period or not period.submissions_open:
        flash('That play period is not open for submissions.', 'danger')
        return redirect(url_for('player.character', name=name))

    # Collect checked criteria IDs from dynamic form
    try:
        claimed_criteria_ids = [
            int(cid) for cid in request.form.getlist('criteria_ids')
        ]
    except (ValueError, TypeError):
        flash('Invalid criteria selection.', 'danger')
        return redirect(url_for('player.character', name=name))

    if not claimed_criteria_ids:
        flash('Please select at least one XP category to claim.', 'danger')
        return redirect(url_for('player.character', name=name))

    # RP links submitted as one per form field (or newline-separated textarea)
    rp_links = [ln.strip() for ln in request.form.getlist('rp_links') if ln.strip()]

    # Staff / helper path
    path = request.form.get('path', 'none').strip()
    if path not in ('none', 'staff', 'helper'):
        path = 'none'
    helper_note = request.form.get('helper_note', '').strip()
    if path == 'helper' and not helper_note:
        flash('A note is required for Helper Activity claims.', 'danger')
        return redirect(url_for('player.character', name=name))

    try:
        discord_name = session.get('discord_name', 'unknown')
        claim = db_service.submit_xp_claim(
            character_name=name,
            play_period=play_period,
            claimed_criteria_ids=claimed_criteria_ids,
            rp_links=rp_links,
            path=path,
            helper_note=helper_note,
        )
        if sheets_sync:
            sheets_sync.sync_add_claim(name, play_period, {})
        n = len(claimed_criteria_ids)
        db_service.log_action(
            staff_user=f'player:{discord_name}',
            action_type='player_claim_submitted',
            target=name,
            details=f'Claimed {claim.computed_xp} XP for {play_period} ({n} criteria)',
        )
        if sheets_sync:
            sheets_sync.sync_log_action(
                staff_user=f'player:{discord_name}',
                action_type='player_claim_submitted',
                target=name,
                details=f'Claimed {claim.computed_xp} XP for {play_period}',
            )
        flash(
            f'XP claim submitted for {play_period} — {claim.computed_xp} XP across '
            f'{n} categor{"y" if n == 1 else "ies"}. Awaiting staff review.',
            'success',
        )
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('player.character', name=name))


@bp.route('/<name>/spend', methods=['POST'])
@require_character_owner
def submit_spend(name):
    """Submit a spend request."""
    char = db_service.get_character(name)
    if not char or not char.active:
        abort(404)

    spend_category = request.form.get('spend_category', '').strip()
    trait_name = request.form.get('trait_name', '').strip()
    justification = request.form.get('justification', '').strip()

    if not spend_category or not trait_name:
        flash('Category and trait name are required.', 'danger')
        return redirect(url_for('player.character', name=name))

    if spend_category not in SPEND_CATEGORIES:
        flash('Invalid spend category.', 'danger')
        return redirect(url_for('player.character', name=name))

    try:
        current_dots = int(request.form.get('current_dots', 0))
        new_dots = int(request.form.get('new_dots', 1))
    except (ValueError, TypeError):
        flash('Invalid dot values.', 'danger')
        return redirect(url_for('player.character', name=name))

    # Humanity conditional flags (player self-certifies all three)
    is_humanity = spend_category == 'Humanity'
    humanity_no_frenzy = bool(request.form.get('humanity_no_frenzy')) if is_humanity else False
    humanity_no_stains = bool(request.form.get('humanity_no_stains')) if is_humanity else False
    humanity_humane_act = bool(request.form.get('humanity_humane_act')) if is_humanity else False

    if not justification:
        flash('Please provide a justification for your spend request.', 'danger')
        return redirect(url_for('player.character', name=name))
    if current_dots < 0 or new_dots < 0 or new_dots > 10:
        flash('Dot ratings must be between 0 and 10.', 'danger')
        return redirect(url_for('player.character', name=name))

    try:
        discord_name = session.get('discord_name', 'unknown')
        xp_cost = db_service.submit_spend_request(
            character_name=name,
            spend_category=spend_category,
            trait_name=trait_name,
            current_dots=current_dots,
            new_dots=new_dots,
            justification=justification,
            humanity_no_frenzy=humanity_no_frenzy,
            humanity_no_stains=humanity_no_stains,
            humanity_humane_act=humanity_humane_act,
        )
        if sheets_sync:
            sheets_sync.sync_add_spend(
                character_name=name,
                spend_category=spend_category,
                trait_name=trait_name,
                current_dots=current_dots,
                new_dots=new_dots,
                justification=justification,
            )
        db_service.log_action(
            staff_user=f'player:{discord_name}',
            action_type='player_spend_submitted',
            target=name,
            details=f'{spend_category}: {trait_name} ({current_dots}→{new_dots}) for {xp_cost} XP',
        )
        if sheets_sync:
            sheets_sync.sync_log_action(
                staff_user=f'player:{discord_name}',
                action_type='player_spend_submitted',
                target=name,
                details=f'{spend_category}: {trait_name} ({current_dots}→{new_dots}) for {xp_cost} XP',
            )
        flash(
            f'Spend request submitted: {trait_name} '
            f'({current_dots}→{new_dots}) for {xp_cost} XP. '
            f'Awaiting staff review.',
            'success',
        )
    except ValueError as e:
        flash(f'Invalid spend request: {e}', 'danger')

    return redirect(url_for('player.character', name=name))
