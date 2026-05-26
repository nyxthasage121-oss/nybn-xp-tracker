"""Coterie management routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app import db_service
from app.auth import require_staff, get_staff_user
from app.db import COTERIE_MAX_MEMBERS
from app.db_service import DBService

bp = Blueprint('coteries', __name__)


@bp.route('/')
@require_staff
def list_coteries():
    coteries = db_service.get_all_coteries()
    # Characters not yet in any coterie (for the creation form member picker)
    taken = {m.lower() for c in coteries for m in c.members}
    active_chars = db_service.get_active_characters()
    available_chars = sorted(
        [c for c in active_chars if c.character_name.lower() not in taken],
        key=lambda c: c.character_name,
    )
    pending_requests = db_service.get_coterie_requests(status='Pending')
    return render_template('coteries/list.html', coteries=coteries,
                           coterie_max=COTERIE_MAX_MEMBERS,
                           available_chars=available_chars,
                           pending_requests=pending_requests)


@bp.route('/<int:coterie_id>')
@require_staff
def detail(coterie_id: int):
    coterie = db_service.get_coterie(coterie_id)
    if not coterie:
        abort(404)

    member_xp = {}
    member_clan = {}
    for name in coterie.members:
        totals = db_service.get_xp_totals(name)
        member_xp[name] = totals.get('available_xp', 0)
        char = db_service.get_character(name)
        member_clan[name] = char.clan if char else ''

    # Characters eligible to add: active, not already in any coterie
    all_coteries = db_service.get_all_coteries()
    taken = {m.lower() for c in all_coteries for m in c.members}
    active_chars = db_service.get_active_characters()
    available_chars = [c for c in active_chars
                       if c.character_name.lower() not in taken]

    all_spends = db_service.get_coterie_spends(coterie_id)
    pending_spends = [s for s in all_spends if s['status'] in ('Pending', 'Funded')]
    spend_history = [s for s in all_spends if s['status'] in ('Approved', 'Denied')]

    sites = db_service.get_coterie_sites(coterie_id)

    merits = db_service.get_coterie_merits(coterie_id)
    flaws = db_service.get_coterie_flaws(coterie_id)
    creation_budget = db_service.get_creation_dot_budget(coterie_id)
    pending_merits = [m for m in merits if m.status == 'Pending']
    approved_merits = [m for m in merits if m.status == 'Approved']

    # Group approved merits by background name for the registry view.
    # Track creation/donated pool separately so the cap indicator is accurate.
    _merit_cap = DBService.COTERIE_MERIT_CAP
    _groups: dict = {}
    for m in approved_merits:
        key = m.merit_name.strip().lower()
        if key not in _groups:
            _groups[key] = {'name': m.merit_name, 'pool_total': 0, 'total': 0, 'items': []}
        _groups[key]['total'] += m.dots
        if m.merit_type in ('creation', 'donated'):
            _groups[key]['pool_total'] += m.dots
        _groups[key]['items'].append(m)
    grouped_merits = sorted(_groups.values(), key=lambda g: g['name'].lower())

    def _dots(n, mx=5):
        return '●' * n + '○' * (mx - n)

    sites_entitled = (
        0 if coterie.chasse <= 1 else
        1 if coterie.chasse <= 3 else
        2 if coterie.chasse == 4 else 3
    )

    lines = [f'**{coterie.name}**']
    if coterie.description:
        lines.append(f'> {coterie.description}')
    lines.append('')
    lines.append(
        f'**Chasse:** {_dots(coterie.chasse)}  ·  '
        f'**Lien:** {_dots(coterie.lien)}  ·  '
        f'**Portillon:** {_dots(coterie.portillon)}'
    )
    if approved_merits:
        lines.append('')
        lines.append('**Merits & Advantages:**')
        for m in sorted(approved_merits, key=lambda x: (x.character_name, x.merit_name)):
            lines.append(f'- {m.character_name}: {m.merit_name} ×{m.dots}')
    if sites:
        lines.append('')
        lines.append('**Sites Owned:**')
        for s in sites:
            lines.append(f'- {s.name} ({s.borough})')
    if coterie.members:
        lines.append('')
        lines.append('**Members:**')
        for name in sorted(coterie.members):
            char = db_service.get_character(name)
            if char and char.player_discord:
                lines.append(f'- {name} (<@{char.player_discord}>)')
            else:
                lines.append(f'- {name}')
    lines.append('')
    lines.append(f'*Formed: {coterie.created_at}*')
    discord_export = '\n'.join(lines)

    return render_template(
        'coteries/detail.html',
        coterie=coterie,
        member_xp=member_xp,
        member_clan=member_clan,
        available_chars=available_chars,
        pending_spends=pending_spends,
        spend_history=spend_history,
        coterie_max=COTERIE_MAX_MEMBERS,
        sites=sites,
        sites_entitled=sites_entitled,
        discord_export=discord_export,
        merits=merits,
        flaws=flaws,
        creation_budget=creation_budget,
        pending_merits=pending_merits,
        approved_merits=approved_merits,
        grouped_merits=grouped_merits,
        merit_cap=_merit_cap,
    )


@bp.route('/create', methods=['POST'])
@require_staff
def create():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    founding_members = request.form.getlist('founding_members')

    if not name:
        flash('Coterie name is required.', 'danger')
        return redirect(url_for('coteries.list_coteries'))

    if len(founding_members) < 3:
        flash('A coterie requires at least 3 founding members.', 'danger')
        return redirect(url_for('coteries.list_coteries'))

    try:
        coterie = db_service.create_coterie(name=name, description=description,
                                            staff_user=get_staff_user())
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('coteries.list_coteries'))

    added, errors = [], []
    for member in founding_members:
        try:
            db_service.add_coterie_member(coterie.coterie_id, member, get_staff_user())
            added.append(member)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        flash(
            f'Coterie "{name}" created with {len(added)} member(s). '
            f'Errors: {"; ".join(errors)}',
            'warning',
        )
    else:
        flash(f'Coterie "{name}" created with {len(added)} founding members.', 'success')
    return redirect(url_for('coteries.detail', coterie_id=coterie.coterie_id))


@bp.route('/<int:coterie_id>/add-member', methods=['POST'])
@require_staff
def add_member(coterie_id: int):
    character_name = request.form.get('character_name', '').strip()
    if not character_name:
        flash('Select a character to add.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    try:
        db_service.add_coterie_member(coterie_id, character_name, get_staff_user())
        flash(f'{character_name} added to coterie.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/remove-member', methods=['POST'])
@require_staff
def remove_member(coterie_id: int):
    character_name = request.form.get('character_name', '').strip()
    if not character_name:
        flash('Character name is required.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    try:
        db_service.remove_coterie_member(coterie_id, character_name, get_staff_user())
        flash(f'{character_name} removed from coterie.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/submit-spend', methods=['POST'])
@require_staff
def submit_spend(coterie_id: int):
    coterie = db_service.get_coterie(coterie_id)
    if not coterie:
        abort(404)

    spend_category = request.form.get('spend_category', '').strip()
    trait_name = request.form.get('trait_name', '').strip()
    xp_per_raw = request.form.get('xp_cost_per_member', '').strip()
    initiated_by = request.form.get('initiated_by', '').strip()
    justification = request.form.get('justification', '').strip()

    if not spend_category or not trait_name or not xp_per_raw or not initiated_by:
        flash('All required fields must be filled.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))

    try:
        xp_per = int(xp_per_raw)
        if xp_per <= 0:
            raise ValueError('XP cost must be greater than zero.')
    except ValueError as exc:
        flash(str(exc) if 'zero' in str(exc) else 'XP cost must be a whole number.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))

    try:
        db_service.submit_coterie_spend(
            coterie_id=coterie_id,
            initiated_by=initiated_by,
            spend_category=spend_category,
            trait_name=trait_name,
            xp_cost_per_member=xp_per,
            justification=justification,
        )
        member_count = len(coterie.members)
        flash(
            f'Coterie spend submitted: {spend_category} — {trait_name}. '
            f'{xp_per} XP × {member_count} members = {xp_per * member_count} XP total.',
            'success',
        )
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/spends/<int:spend_id>/commit', methods=['POST'])
@require_staff
def commit_member(coterie_id: int, spend_id: int):
    character_name = request.form.get('character_name', '').strip()
    if not character_name:
        flash('Character name is required.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    try:
        result = db_service.commit_coterie_contribution(spend_id, character_name)
        if result['all_committed']:
            flash(f'{character_name} committed — all members funded. Ready for staff approval.',
                  'success')
        else:
            remaining = len(result['members_remaining'])
            flash(f'{character_name} committed. {remaining} member(s) still pending.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/spends/<int:spend_id>/commit-all', methods=['POST'])
@require_staff
def commit_all(coterie_id: int, spend_id: int):
    coterie = db_service.get_coterie(coterie_id)
    if not coterie:
        abort(404)

    spends = db_service.get_coterie_spends(coterie_id)
    spend = next((s for s in spends if s['id'] == spend_id), None)
    if not spend:
        flash('Spend not found.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    if spend['status'] != 'Pending':
        flash(f'Spend is already {spend["status"]} — cannot commit.', 'warning')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))

    committed_lower = {k.lower() for k in spend['contributions']}
    uncommitted = [m for m in coterie.members if m.lower() not in committed_lower]

    committed_count = 0
    for member in uncommitted:
        try:
            db_service.commit_coterie_contribution(spend_id, member)
            committed_count += 1
        except ValueError:
            pass

    if committed_count:
        flash(f'Committed {committed_count} remaining member(s). Spend is now Funded — ready for approval.',
              'success')
    else:
        flash('All members were already committed.', 'info')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/spends/<int:spend_id>/approve', methods=['POST'])
@require_staff
def approve_spend(coterie_id: int, spend_id: int):
    notes = request.form.get('notes', '').strip()
    try:
        db_service.approve_coterie_spend(spend_id, get_staff_user(), notes)
        flash('Coterie spend approved. XP deducted from all members.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/spends/<int:spend_id>/deny', methods=['POST'])
@require_staff
def deny_spend(coterie_id: int, spend_id: int):
    notes = request.form.get('notes', '').strip()
    try:
        db_service.deny_coterie_spend(spend_id, get_staff_user(), notes)
        flash('Coterie spend denied.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/edit', methods=['POST'])
@require_staff
def edit(coterie_id: int):
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    try:
        db_service.update_coterie(coterie_id, name, description, get_staff_user())
        flash('Coterie updated.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/archive', methods=['POST'])
@require_staff
def archive(coterie_id: int):
    try:
        db_service.archive_coterie(coterie_id, get_staff_user())
        flash('Coterie archived.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/unarchive', methods=['POST'])
@require_staff
def unarchive(coterie_id: int):
    try:
        db_service.unarchive_coterie(coterie_id, get_staff_user())
        flash('Coterie unarchived.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/merits/submit', methods=['POST'])
@require_staff
def submit_merit(coterie_id: int):
    character_name = request.form.get('character_name', '').strip()
    merit_name = request.form.get('merit_name', '').strip()
    dots_raw = request.form.get('dots', '').strip()
    merit_type = request.form.get('merit_type', 'purchased').strip()
    justification = request.form.get('justification', '').strip()

    if not character_name or not merit_name or not dots_raw:
        flash('Character, merit name, and dots are required.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    try:
        dots = int(dots_raw)
    except ValueError:
        flash('Dots must be a whole number.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))

    try:
        merit = db_service.submit_coterie_merit(
            coterie_id=coterie_id,
            character_name=character_name,
            merit_name=merit_name,
            dots=dots,
            merit_type=merit_type,
            justification=justification,
        )
        if merit.status == 'Approved':
            flash(f'{character_name}: {merit_name} ×{dots} recorded.', 'success')
        else:
            flash(
                f'Merit request submitted: {merit_name} ×{dots} for {character_name}. '
                f'Awaiting staff approval.',
                'success',
            )
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/merits/<int:merit_id>/approve', methods=['POST'])
@require_staff
def approve_merit(coterie_id: int, merit_id: int):
    notes = request.form.get('notes', '').strip()
    try:
        db_service.approve_coterie_merit(merit_id, get_staff_user(), notes)
        flash('Merit approved.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/merits/<int:merit_id>/deny', methods=['POST'])
@require_staff
def deny_merit(coterie_id: int, merit_id: int):
    notes = request.form.get('notes', '').strip()
    try:
        db_service.deny_coterie_merit(merit_id, get_staff_user(), notes)
        flash('Merit denied.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/flaws/add', methods=['POST'])
@require_staff
def add_flaw(coterie_id: int):
    flaw_name = request.form.get('flaw_name', '').strip()
    dots_raw = request.form.get('dots_granted', '').strip()

    if not flaw_name or not dots_raw:
        flash('Flaw name and dots are required.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    try:
        dots = int(dots_raw)
    except ValueError:
        flash('Dots must be a whole number.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))

    try:
        flaw = db_service.add_coterie_flaw(coterie_id, flaw_name, dots, get_staff_user())
        flash(f'Flaw "{flaw_name}" added (+{flaw.dots_granted} creation dots).', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/flaws/<int:flaw_id>/remove', methods=['POST'])
@require_staff
def remove_flaw(coterie_id: int, flaw_id: int):
    try:
        db_service.remove_coterie_flaw(flaw_id, get_staff_user())
        flash('Flaw removed.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))


@bp.route('/<int:coterie_id>/delete', methods=['POST'])
@require_staff
def delete(coterie_id: int):
    try:
        db_service.delete_coterie(coterie_id, get_staff_user())
        flash('Coterie permanently deleted.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.list_coteries'))


@bp.route('/requests/<int:request_id>/acknowledge', methods=['POST'])
@require_staff
def acknowledge_request(request_id: int):
    notes = request.form.get('notes', '').strip()
    try:
        db_service.acknowledge_coterie_request(request_id, get_staff_user(), notes)
        flash('Coterie request acknowledged — use the New Coterie form to create it.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.list_coteries'))


@bp.route('/requests/<int:request_id>/deny', methods=['POST'])
@require_staff
def deny_request(request_id: int):
    notes = request.form.get('notes', '').strip()
    try:
        db_service.deny_coterie_request(request_id, get_staff_user(), notes)
        flash('Coterie formation request denied.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.list_coteries'))


@bp.route('/<int:coterie_id>/update-ratings', methods=['POST'])
@require_staff
def update_ratings(coterie_id: int):
    try:
        chasse = int(request.form.get('chasse', 0))
        lien = int(request.form.get('lien', 0))
        portillon = int(request.form.get('portillon', 0))
    except (ValueError, TypeError):
        flash('Ratings must be whole numbers.', 'danger')
        return redirect(url_for('coteries.detail', coterie_id=coterie_id))
    try:
        db_service.update_coterie_ratings(coterie_id, chasse, lien, portillon, get_staff_user())
        flash(f'Ratings updated — Chasse {chasse} / Lien {lien} / Portillon {portillon}.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('coteries.detail', coterie_id=coterie_id))
