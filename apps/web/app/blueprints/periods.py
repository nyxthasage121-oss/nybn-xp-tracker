"""Play period management routes."""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash
)
from app import db_service, sheets_sync
from app.auth import require_staff, get_staff_user
from app.models import PlayPeriod, ChronicleSettings

bp = Blueprint('periods', __name__)


@bp.route('/')
@require_staff
def list_periods():
    """List all play periods."""
    periods = db_service.get_all_periods()
    # Most recent first
    periods.sort(key=lambda p: p.night_number, reverse=True)
    return render_template('periods/list.html', periods=periods)


@bp.route('/add', methods=['GET'])
@require_staff
def add_form():
    """Show form to create a new play period."""
    next_night = db_service.get_next_night_number()
    return render_template('periods/add.html', next_night=next_night)


@bp.route('/add', methods=['POST'])
@require_staff
def add():
    """Create a new play period."""
    period_type = request.form.get('period_type', 'night').strip()
    night_number = int(request.form.get('night_number', 0))
    start_date = request.form.get('start_date', '')
    end_date = request.form.get('end_date', '')
    session_number = int(request.form.get('session_number', 0))

    # Build the period label
    start_short = start_date[5:].replace('-', '/') if start_date else ''
    end_short = end_date[5:].replace('-', '/') if end_date else ''
    if start_short:
        parts = start_short.split('/')
        start_short = f'{int(parts[0])}/{int(parts[1])}'
    if end_short:
        parts = end_short.split('/')
        end_short = f'{int(parts[0])}/{int(parts[1])}'

    if period_type == 'night':
        label = f'Night {night_number} - {start_short} - {end_short}'
    elif period_type == 'downtime':
        label = f'Downtime - {start_short} - {end_short}'
    else:
        label = f'Timeskip - {start_short} - {end_short}'

    period = PlayPeriod(
        period_label=label,
        night_number=night_number if period_type == 'night' else 0,
        start_date=start_date.replace('-', ''),
        end_date=end_date.replace('-', ''),
        session_number=session_number,
        submissions_open=(period_type == 'night'),
        active=True,
        period_type=period_type,
    )

    db_service.create_period(period)
    if sheets_sync:
        sheets_sync.sync_create_period(period)

    staff = get_staff_user()
    db_service.log_action(
        staff_user=staff,
        action_type='create_period',
        target=label,
        details=f'Created play period: {label} (Session {session_number})',
    )
    if sheets_sync:
        sheets_sync.sync_log_action(
            staff_user=staff, action_type='create_period',
            target=label, details=f'Created play period: {label} (Session {session_number})',
        )

    flash(f'Created {label}.', 'success')
    return redirect(url_for('periods.list_periods'))


@bp.route('/import', methods=['GET', 'POST'])
@require_staff
def import_periods():
    """Import play periods from a master XP spreadsheet."""
    if request.method == 'GET':
        return render_template('periods/import.html', periods=None, sheet_url='')

    action = request.form.get('action', 'preview')
    sheet_url = request.form.get('sheet_url', '').strip()

    if action == 'preview':
        if not sheet_url:
            flash('Please paste a Google Sheet URL.', 'danger')
            return redirect(url_for('periods.import_periods'))
        try:
            periods = db_service.preview_period_import(sheet_url)
        except Exception as e:
            flash(f'Error reading spreadsheet: {e}', 'danger')
            return redirect(url_for('periods.import_periods'))

        if not periods:
            flash('No play period tabs found.', 'warning')
            return redirect(url_for('periods.import_periods'))

        new_count = sum(1 for p in periods if not p['already_exists'])
        return render_template(
            'periods/import.html',
            periods=periods,
            sheet_url=sheet_url,
            new_count=new_count,
        )

    elif action == 'confirm':
        if not sheet_url:
            flash('Missing spreadsheet URL.', 'danger')
            return redirect(url_for('periods.import_periods'))

        try:
            periods = db_service.preview_period_import(sheet_url)
            staff = get_staff_user()
            count = db_service.bulk_add_periods(periods, staff)
            db_service.log_action(
                staff_user=staff,
                action_type='period_import',
                target='Play Periods',
                details=f'Imported {count} play periods from master spreadsheet',
            )
            if sheets_sync:
                sheets_sync.sync_log_action(
                    staff_user=staff, action_type='period_import',
                    target='Play Periods',
                    details=f'Imported {count} play periods from master spreadsheet',
                )
            flash(f'Successfully imported {count} play periods.', 'success')
        except Exception as e:
            flash(f'Import failed: {e}', 'danger')

        return redirect(url_for('periods.list_periods'))

    return redirect(url_for('periods.import_periods'))


@bp.route('/<path:label>/toggle-submissions', methods=['POST'])
@require_staff
def toggle_submissions(label):
    """Toggle whether submissions are open for a period."""
    periods = db_service.get_all_periods()
    period = next((p for p in periods if p.period_label == label), None)
    if not period:
        flash('Period not found.', 'danger')
        return redirect(url_for('periods.list_periods'))

    new_value = 'FALSE' if period.submissions_open else 'TRUE'
    db_service.update_period(label, {'submissions_open': new_value})

    status = 'opened' if new_value == 'TRUE' else 'closed'
    flash(f'Submissions {status} for {label}.', 'success')
    return redirect(request.referrer or url_for('periods.list_periods'))


@bp.route('/<path:label>/toggle-active', methods=['POST'])
@require_staff
def toggle_active(label):
    """Toggle whether a period shows in form dropdowns."""
    periods = db_service.get_all_periods()
    period = next((p for p in periods if p.period_label == label), None)
    if not period:
        flash('Period not found.', 'danger')
        return redirect(url_for('periods.list_periods'))

    new_value = 'FALSE' if period.active else 'TRUE'
    db_service.update_period(label, {'active': new_value})

    status = 'activated' if new_value == 'TRUE' else 'deactivated'
    flash(f'{label} {status} in form dropdowns.', 'success')
    return redirect(url_for('periods.list_periods'))


@bp.route('/settings', methods=['GET', 'POST'])
@require_staff
def settings():
    """View/edit chronicle schedule settings."""
    current = db_service.get_chronicle_settings()

    if request.method == 'POST':
        try:
            new_settings = ChronicleSettings(
                server_start_date=request.form.get('server_start_date', '').strip() or '2023-04-13',
                timeskip_interval_weeks=int(request.form.get('timeskip_interval_weeks', 8)),
                night_duration_days=int(request.form.get('night_duration_days', 12)),
                downtime_duration_days=int(request.form.get('downtime_duration_days', 2)),
                notes=request.form.get('notes', '').strip(),
            )
            db_service.save_chronicle_settings(new_settings)
            db_service.log_action(
                staff_user=get_staff_user(),
                action_type='update_chronicle_settings',
                target='Chronicle Settings',
                details=(
                    f'Timeskip every {new_settings.timeskip_interval_weeks} weeks, '
                    f'night={new_settings.night_duration_days}d, '
                    f'downtime={new_settings.downtime_duration_days}d'
                ),
            )
            flash('Chronicle settings saved.', 'success')
        except (ValueError, TypeError) as exc:
            flash(f'Invalid value: {exc}', 'danger')
        return redirect(url_for('periods.settings'))

    nights_per_cycle = max(1, current.timeskip_interval_weeks // 2)
    return render_template(
        'periods/settings.html',
        settings=current,
        nights_per_cycle=nights_per_cycle,
    )


@bp.route('/generate', methods=['POST'])
@require_staff
def generate():
    """Auto-generate upcoming nights based on chronicle settings."""
    try:
        count = max(1, min(12, int(request.form.get('count', 4))))
    except (ValueError, TypeError):
        count = 4

    created = db_service.generate_upcoming_nights(count)

    if created:
        labels = ', '.join(p.period_label for p in created)
        flash(f'Generated {len(created)} period(s): {labels}', 'success')
        db_service.log_action(
            staff_user=get_staff_user(),
            action_type='generate_periods',
            target='Play Periods',
            details=f'Auto-generated {len(created)} periods: {labels}',
        )
    else:
        flash('No new periods generated (they may already exist).', 'info')

    return redirect(url_for('periods.list_periods'))
