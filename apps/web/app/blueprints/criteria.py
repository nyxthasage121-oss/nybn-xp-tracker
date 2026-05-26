"""Criteria admin panel — add, edit, toggle, and remove XP earn criteria."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db_service
from app.auth import require_staff

bp = Blueprint('criteria', __name__)


@bp.route('/')
@require_staff
def list_criteria():
    criteria = db_service.get_all_criteria()
    return render_template('criteria/list.html', criteria=criteria)


@bp.route('/add', methods=['POST'])
@require_staff
def add_criterion():
    label = request.form.get('label', '').strip()
    description = request.form.get('description', '').strip()
    xp_value_raw = request.form.get('xp_value', '').strip()
    category = request.form.get('category', 'base').strip()
    requires_rp_links = bool(request.form.get('requires_rp_links'))
    requires_text_note = bool(request.form.get('requires_text_note'))
    sort_order_raw = request.form.get('sort_order', '0').strip()

    if not label:
        flash('Label is required.', 'danger')
        return redirect(url_for('criteria.list_criteria'))

    try:
        xp_value = int(xp_value_raw)
    except (ValueError, TypeError):
        flash('XP value must be a whole number.', 'danger')
        return redirect(url_for('criteria.list_criteria'))

    if category not in ('base', 'player', 'staff', 'helper'):
        flash('Invalid category.', 'danger')
        return redirect(url_for('criteria.list_criteria'))

    try:
        sort_order = int(sort_order_raw)
    except (ValueError, TypeError):
        sort_order = 0

    db_service.add_criterion(
        label=label,
        description=description or None,
        xp_value=xp_value,
        category=category,
        requires_rp_links=requires_rp_links,
        requires_text_note=requires_text_note,
        sort_order=sort_order,
    )
    flash(f'Criterion "{label}" added.', 'success')
    return redirect(url_for('criteria.list_criteria'))


@bp.route('/<int:criterion_id>/edit', methods=['POST'])
@require_staff
def edit_criterion(criterion_id: int):
    label = request.form.get('label', '').strip()
    description = request.form.get('description', '').strip()
    xp_value_raw = request.form.get('xp_value', '').strip()
    category = request.form.get('category', 'base').strip()
    requires_rp_links = bool(request.form.get('requires_rp_links'))
    requires_text_note = bool(request.form.get('requires_text_note'))
    sort_order_raw = request.form.get('sort_order', '0').strip()

    if not label:
        flash('Label is required.', 'danger')
        return redirect(url_for('criteria.list_criteria'))

    try:
        xp_value = int(xp_value_raw)
    except (ValueError, TypeError):
        flash('XP value must be a whole number.', 'danger')
        return redirect(url_for('criteria.list_criteria'))

    if category not in ('base', 'player', 'staff', 'helper'):
        flash('Invalid category.', 'danger')
        return redirect(url_for('criteria.list_criteria'))

    try:
        sort_order = int(sort_order_raw)
    except (ValueError, TypeError):
        sort_order = 0

    db_service.update_criterion(criterion_id, {
        'label': label,
        'description': description,
        'xp_value': xp_value,
        'category': category,
        'requires_rp_links': requires_rp_links,
        'requires_text_note': requires_text_note,
        'sort_order': sort_order,
    })
    flash(f'Criterion "{label}" updated.', 'success')
    return redirect(url_for('criteria.list_criteria'))


@bp.route('/<int:criterion_id>/toggle', methods=['POST'])
@require_staff
def toggle_criterion(criterion_id: int):
    db_service.toggle_criterion(criterion_id)
    return redirect(url_for('criteria.list_criteria'))


@bp.route('/<int:criterion_id>/delete', methods=['POST'])
@require_staff
def delete_criterion(criterion_id: int):
    db_service.remove_criterion(criterion_id)
    flash('Criterion removed.', 'success')
    return redirect(url_for('criteria.list_criteria'))
