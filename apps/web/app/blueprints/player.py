"""Player-facing routes. Requires Discord authentication."""

import json as _json

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

    # Parse Progeny character sheet JSON into display-ready structures
    sheet_data = None
    sheet_ctx: dict = {}
    if char.sheet_json:
        try:
            raw = _json.loads(char.sheet_json)
            if isinstance(raw, dict) and 'attributes' in raw and 'skills' in raw:
                sheet_data = raw
                # Group disciplines by discipline name, sorted by level
                discs: dict = {}
                for power in raw.get('disciplines', []):
                    disc = power.get('discipline', 'Unknown')
                    discs.setdefault(disc, []).append(power)
                for disc in discs:
                    discs[disc].sort(key=lambda p: p.get('level', 0))
                # Group rituals and ceremonies similarly
                rituals: dict = {}
                for r in raw.get('rituals', []):
                    disc = r.get('discipline', 'Blood Sorcery')
                    rituals.setdefault(disc, []).append(r)
                ceremonies: dict = {}
                for c in raw.get('ceremonies', []):
                    disc = c.get('discipline', 'Oblivion')
                    ceremonies.setdefault(disc, []).append(c)
                # Index skill specialties by skill name
                specs: dict = {}
                for s in raw.get('skillSpecialties', []):
                    skill = s.get('skill', '')
                    if skill:
                        specs.setdefault(skill, []).append(s.get('specialty', ''))
                sheet_ctx = {
                    'disciplines_grouped': discs,
                    'rituals_grouped': rituals,
                    'ceremonies_grouped': ceremonies,
                    'specialties': specs,
                }
        except (ValueError, KeyError, TypeError):
            sheet_data = None

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
        sheet_data=sheet_data,
        sheet_ctx=sheet_ctx,
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


_BOROUGH_ORDER = ['Manhattan', 'Brooklyn', 'Queens', 'The Bronx', 'Staten Island']


@bp.route('/coteries')
@require_login
def coteries():
    """Read-only coterie list + formation request form for players."""
    from app.db import COTERIE_MAX_MEMBERS
    all_coteries = db_service.get_all_coteries()
    active_coteries = [c for c in all_coteries if c.active]
    inactive_coteries = [c for c in all_coteries if not c.active]

    discord_id = get_player_discord_id()
    # Show this player's own requests
    all_requests = db_service.get_coterie_requests()
    my_requests = [r for r in all_requests if r.submitted_by_discord_id == discord_id]

    return render_template(
        'player/coteries.html',
        active_coteries=active_coteries,
        inactive_coteries=inactive_coteries,
        my_requests=my_requests,
        coterie_max=COTERIE_MAX_MEMBERS,
    )


@bp.route('/coteries/request', methods=['POST'])
@require_login
def submit_coterie_request():
    """Player submits a coterie formation request."""
    discord_id = get_player_discord_id()
    discord_name = session.get('discord_name', 'unknown')

    name = request.form.get('name', '').strip()
    notes = request.form.get('notes', '').strip()
    has_enough_members = bool(request.form.get('has_enough_members'))
    members_have_met = bool(request.form.get('members_have_met'))

    if not name:
        flash('Coterie name is required.', 'danger')
        return redirect(url_for('player.coteries'))

    if not has_enough_members or not members_have_met:
        flash('Please confirm both requirements before submitting.', 'danger')
        return redirect(url_for('player.coteries'))

    try:
        db_service.submit_coterie_request(
            name=name,
            notes=notes,
            has_enough_members=has_enough_members,
            members_have_met=members_have_met,
            submitted_by=discord_name,
            submitted_by_discord_id=discord_id,
        )
        flash(
            f'Coterie formation request for "{name}" sent to staff.',
            'success',
        )
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('player.coteries'))


@bp.route('/sites')
@require_login
def sites():
    """Read-only hunting sites view for players."""
    all_sites = db_service.get_all_sites()

    by_borough: dict[str, list] = {b: [] for b in _BOROUGH_ORDER}
    for site in all_sites:
        by_borough.setdefault(site.borough, []).append(site)

    return render_template(
        'player/sites.html',
        by_borough=by_borough,
        borough_order=_BOROUGH_ORDER,
    )


@bp.route('/<name>/profile', methods=['POST'])
@require_character_owner
def save_profile(name):
    """Save player-editable IC profile fields."""
    char = db_service.get_character(name)
    if not char or not char.active:
        abort(404)

    discord_name = session.get('discord_name', 'unknown')

    fields = {
        'profile_pronouns':     request.form.get('pronouns', ''),
        'profile_concept':      request.form.get('concept', ''),
        'profile_epitaph':      request.form.get('epitaph', ''),
        'profile_apparent_age': request.form.get('apparent_age', ''),
        'profile_appearance':   request.form.get('appearance', ''),
        'profile_biography':    request.form.get('biography', ''),
    }

    try:
        db_service.save_character_profile(name, fields, discord_name)
        flash('IC Profile saved successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('player.character', name=name))


@bp.route('/<name>/sheet', methods=['POST'])
@require_character_owner
def import_sheet(name):
    """Import a Progeny character sheet JSON export."""
    char = db_service.get_character(name)
    if not char or not char.active:
        abort(404)

    discord_name = session.get('discord_name', 'unknown')
    sheet_json = request.form.get('sheet_json', '').strip()

    if not sheet_json:
        flash('Please paste your Progeny character JSON before importing.', 'danger')
        return redirect(url_for('player.character', name=name))

    try:
        db_service.save_sheet_json(name, sheet_json, discord_name)
        flash('Character sheet imported successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('player.character', name=name))


@bp.route('/<name>/sheet/edit', methods=['GET', 'POST'])
@require_character_owner
def edit_sheet(name):
    """Native character sheet editor — full form-based entry."""
    char = db_service.get_character(name)
    if not char or not char.active:
        abort(404)

    if request.method == 'POST':
        discord_name = session.get('discord_name', 'unknown')
        try:
            sheet_json = _build_sheet_json_from_form(request.form)
            db_service.save_sheet_native(name, sheet_json, discord_name)
            flash('Character sheet saved.', 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('player.character', name=name) + '#char-sheet')

    # GET — parse existing data for pre-population
    sheet_data: dict = {}
    if char.sheet_json:
        try:
            sheet_data = _json.loads(char.sheet_json)
        except (ValueError, TypeError):
            sheet_data = {}

    return render_template('player/sheet_editor.html', char=char, sheet_data=sheet_data)


def _build_sheet_json_from_form(form) -> str:
    """Assemble a Progeny-compatible sheet JSON dict from a POST form."""

    def _int(key: str, default: int = 0) -> int:
        try:
            return max(0, int(form.get(key, default) or default))
        except (ValueError, TypeError):
            return default

    def _str(key: str, default: str = '') -> str:
        return str(form.get(key, default) or '').strip()

    data: dict = {
        'name':         _str('name'),
        'clan':         _str('clan'),
        'generation':   _int('generation', 13),
        'sect':         _str('sect'),
        'predatorType': _str('predatorType'),
        'sire':         _str('sire'),
        'ambition':     _str('ambition'),
        'desire':       _str('desire'),
        'bloodPotency': _int('bloodPotency', 0),
        'humanity':     _int('humanity', 7),
        'maxHealth':    _int('maxHealth', 4),
        'willpower':    _int('willpower', 3),
        'attributes': {
            'strength':     max(1, _int('attr_strength',     1)),
            'dexterity':    max(1, _int('attr_dexterity',    1)),
            'stamina':      max(1, _int('attr_stamina',      1)),
            'charisma':     max(1, _int('attr_charisma',     1)),
            'manipulation': max(1, _int('attr_manipulation', 1)),
            'composure':    max(1, _int('attr_composure',    1)),
            'intelligence': max(1, _int('attr_intelligence', 1)),
            'wits':         max(1, _int('attr_wits',         1)),
            'resolve':      max(1, _int('attr_resolve',      1)),
        },
        'skills': {
            'athletics':    _int('skill_athletics',     0),
            'brawl':        _int('skill_brawl',         0),
            'craft':        _int('skill_craft',         0),
            'drive':        _int('skill_drive',         0),
            'firearms':     _int('skill_firearms',      0),
            'melee':        _int('skill_melee',         0),
            'larceny':      _int('skill_larceny',       0),
            'stealth':      _int('skill_stealth',       0),
            'survival':     _int('skill_survival',      0),
            'animal ken':   _int('skill_animal_ken',    0),
            'etiquette':    _int('skill_etiquette',     0),
            'insight':      _int('skill_insight',       0),
            'intimidation': _int('skill_intimidation',  0),
            'leadership':   _int('skill_leadership',    0),
            'performance':  _int('skill_performance',   0),
            'persuasion':   _int('skill_persuasion',    0),
            'streetwise':   _int('skill_streetwise',    0),
            'subterfuge':   _int('skill_subterfuge',    0),
            'academics':    _int('skill_academics',     0),
            'awareness':    _int('skill_awareness',     0),
            'finance':      _int('skill_finance',       0),
            'investigation':_int('skill_investigation', 0),
            'medicine':     _int('skill_medicine',      0),
            'occult':       _int('skill_occult',        0),
            'politics':     _int('skill_politics',      0),
            'science':      _int('skill_science',       0),
            'technology':   _int('skill_technology',    0),
        },
    }

    # Skill specialties — parallel lists spec_skill[] / spec_name[]
    specs = []
    for skill, spec in zip(form.getlist('spec_skill'), form.getlist('spec_name')):
        skill = (skill or '').strip()
        spec = (spec or '').strip()
        if skill and spec:
            specs.append({'skill': skill, 'specialty': spec})
    data['skillSpecialties'] = specs

    # Disciplines — flat power list, server groups by discipline name
    disc_disciplines = form.getlist('disc_discipline')
    disc_names       = form.getlist('disc_name')
    disc_levels      = form.getlist('disc_level')
    disc_dice        = form.getlist('disc_dice_pool')
    disc_rouse       = form.getlist('disc_rouse')
    disc_summaries   = form.getlist('disc_summary')
    disc_descs       = form.getlist('disc_desc')

    disciplines = []
    for i, pname in enumerate(disc_names):
        pname = (pname or '').strip()
        if not pname:
            continue
        try:
            lvl = max(1, min(5, int(disc_levels[i]))) if i < len(disc_levels) else 1
        except (ValueError, TypeError):
            lvl = 1
        try:
            rouse = max(0, min(3, int(disc_rouse[i]))) if i < len(disc_rouse) else 0
        except (ValueError, TypeError):
            rouse = 0
        disciplines.append({
            'name':                 pname,
            'discipline':           (disc_disciplines[i].strip() if i < len(disc_disciplines) else ''),
            'level':                lvl,
            'dicePool':             (disc_dice[i].strip()      if i < len(disc_dice)      else ''),
            'rouseChecks':          rouse,
            'summary':              (disc_summaries[i].strip() if i < len(disc_summaries) else ''),
            'description':          (disc_descs[i].strip()     if i < len(disc_descs)     else ''),
            'amalgamPrerequisites': [],
        })
    data['disciplines'] = disciplines
    data['rituals']     = []
    data['ceremonies']  = []

    # Touchstones
    ts_names       = form.getlist('ts_name')
    ts_convictions = form.getlist('ts_conviction')
    ts_descs       = form.getlist('ts_desc')
    touchstones = []
    for i, n in enumerate(ts_names):
        n = (n or '').strip()
        if not n:
            continue
        touchstones.append({
            'name':        n,
            'conviction':  (ts_convictions[i].strip() if i < len(ts_convictions) else ''),
            'description': (ts_descs[i].strip()       if i < len(ts_descs)       else ''),
        })
    data['touchstones'] = touchstones

    # Merits
    merit_names    = form.getlist('merit_name')
    merit_levels   = form.getlist('merit_level')
    merit_summaries= form.getlist('merit_summary')
    merits = []
    for i, n in enumerate(merit_names):
        n = (n or '').strip()
        if not n:
            continue
        try:
            lvl = max(1, min(5, int(merit_levels[i]))) if i < len(merit_levels) else 1
        except (ValueError, TypeError):
            lvl = 1
        merits.append({
            'name':    n,
            'level':   lvl,
            'summary': (merit_summaries[i].strip() if i < len(merit_summaries) else ''),
        })
    data['merits'] = merits

    # Flaws
    flaw_names    = form.getlist('flaw_name')
    flaw_levels   = form.getlist('flaw_level')
    flaw_summaries= form.getlist('flaw_summary')
    flaws = []
    for i, n in enumerate(flaw_names):
        n = (n or '').strip()
        if not n:
            continue
        try:
            lvl = max(1, min(5, int(flaw_levels[i]))) if i < len(flaw_levels) else 1
        except (ValueError, TypeError):
            lvl = 1
        flaws.append({
            'name':    n,
            'level':   lvl,
            'summary': (flaw_summaries[i].strip() if i < len(flaw_summaries) else ''),
        })
    data['flaws'] = flaws

    # Ephemeral state
    data['ephemeral'] = {
        'hunger':                     _int('hunger',                     1),
        'superficialDamage':          _int('superficialDamage',          0),
        'aggravatedDamage':           _int('aggravatedDamage',           0),
        'superficialWillpowerDamage': _int('superficialWillpowerDamage', 0),
        'aggravatedWillpowerDamage':  _int('aggravatedWillpowerDamage',  0),
        'humanityStains':             _int('humanityStains',             0),
        'experienceSpent':            _int('experienceSpent',            0),
    }

    return _json.dumps(data)


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
