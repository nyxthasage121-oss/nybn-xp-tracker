"""Chronicle calendar — driven from the PlayPeriod DB table.

`get_calendar()` is called from the player blueprint and returns a list of
dicts that the player portal calendar renders.  Falls back to an empty list
if the DB has no periods yet (staff should add them via the admin panel).
"""

import sys
from datetime import date

# Windows uses %#d to strip leading zeros; Linux/macOS use %-d
_DAY_FMT = '%#d' if sys.platform == 'win32' else '%-d'


def _fmt(d: date) -> str:
    return d.strftime(f'%b {_DAY_FMT}')


def _parse_date(s: str) -> date | None:
    """Parse YYYYMMDD or YYYY-MM-DD into a date object."""
    s = s.replace('-', '').strip()
    if len(s) == 8:
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            pass
    return None


def get_calendar() -> list[dict]:
    """Return all play periods from the DB as calendar entries, most recent first.

    Each entry has:
        type        – 'night' | 'downtime' | 'timeskip'
        label       – human-readable period name
        note        – optional annotation (currently always None; reserved for STs)
        start       – date object
        end         – date object
        start_fmt   – formatted string e.g. "May 19"
        end_fmt     – formatted string e.g. "May 31"
        status      – 'past' | 'current' | 'upcoming'
        days_until  – int (upcoming only, else None)
        days_left   – int (current only, else None)
        night_number – int (0 for downtime/timeskip)
    """
    try:
        from app.db import DbPlayPeriod  # noqa: PLC0415 — imported inside to avoid circular
        rows = DbPlayPeriod.query.order_by(DbPlayPeriod.night_number.asc()).all()
    except Exception:
        return []

    if not rows:
        return []

    today = date.today()
    entries = []

    for row in rows:
        start = _parse_date(row.start_date or '')
        end = _parse_date(row.end_date or '')
        if not start or not end:
            continue

        if end < today:
            status = 'past'
        elif start <= today <= end:
            status = 'current'
        else:
            status = 'upcoming'

        days_until = (start - today).days if status == 'upcoming' else None
        days_left = (end - today).days if status == 'current' else None

        entries.append({
            'type':         row.period_type or 'night',
            'label':        row.period_label or '',
            'note':         None,
            'start':        start,
            'end':          end,
            'start_fmt':    _fmt(start),
            'end_fmt':      _fmt(end),
            'status':       status,
            'days_until':   days_until,
            'days_left':    days_left,
            'night_number': row.night_number or 0,
        })

    return entries
