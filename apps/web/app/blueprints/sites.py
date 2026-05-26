"""Hunting sites reference — view all sites and assign coterie ownership."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db_service
from app.auth import require_staff, get_staff_user

bp = Blueprint('sites', __name__)

BOROUGH_ORDER = ['Manhattan', 'Brooklyn', 'Queens', 'The Bronx', 'Staten Island']


@bp.route('/')
@require_staff
def list_sites():
    sites = db_service.get_all_sites()
    coteries = db_service.get_all_coteries()

    by_borough: dict[str, list] = {b: [] for b in BOROUGH_ORDER}
    for site in sites:
        by_borough.setdefault(site.borough, []).append(site)

    return render_template(
        'sites/list.html',
        by_borough=by_borough,
        borough_order=BOROUGH_ORDER,
        coteries=coteries,
    )


@bp.route('/<int:site_id>/assign', methods=['POST'])
@require_staff
def assign(site_id: int):
    raw = request.form.get('coterie_id', '').strip()
    coterie_id = int(raw) if raw and raw.isdigit() else None
    try:
        db_service.assign_site(site_id, coterie_id, get_staff_user())
        flash('Site ownership updated.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('sites.list_sites'))
