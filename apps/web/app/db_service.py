"""DBService — SQLAlchemy-backed data service for NYbN XP Tracker.

All blueprint routes go through this service. Never write to the DB directly
from a blueprint — always call a method here so business rules are enforced
in one place.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func

from app.db import (
    db, XP_CAP, COTERIE_MAX_MEMBERS,
    DbCharacter, DbPlayPeriod, DbCriteria,
    DbXPClaim, DbSpendRequest, DbLedgerEntry, DbAuditLog,
    DbCoterie, DbCoterieMembership, DbCoterieSpend, DbHuntingSite,
    DbChronicleSettings, DbPlayerProfile,
)
from app.models import (
    Character, PlayPeriod, Criteria, XPClaim,
    SpendRequest, LedgerEntry, AuditEntry,
    Coterie, CoterieSpend, HuntingSite,
    ChronicleSettings, PlayerProfile,
    NYBN_SEED_CRITERIA, NYBN_SEED_SITES,
)


def _now_str() -> str:
    return datetime.utcnow().strftime('%Y%m%d %H:%M:%S')


def _today_str() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _parse_yyyymmdd(value: str) -> Optional[datetime]:
    raw = str(value or '').strip()
    if not raw:
        return None
    for fmt in ('%Y%m%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _short_md(value: datetime) -> str:
    return f'{value.month}/{value.day}'


def _jloads(value: str | None, default):
    try:
        return json.loads(value or '') if value else default
    except (json.JSONDecodeError, TypeError):
        return default


# ── Row → dataclass converters ────────────────────────────────────────────────

def _row_to_character(row: DbCharacter) -> Character:
    return Character(
        character_name=row.character_name,
        player_discord=row.player_discord or '',
        player_discord_name=row.player_discord_name or '',
        clan=row.clan or '',
        age_category=row.age_category or '',
        sect=row.sect or '',
        active=bool(row.active),
        creation_xp=row.creation_xp or 0,
        enemy=row.enemy or '',
        date_added=row.date_added or '',
        notes=row.notes or '',
        xp_cap_reached=bool(row.xp_cap_reached),
        xp_cap_reached_date=row.xp_cap_reached_date or '',
        retirement_deadline=row.retirement_deadline or '',
        retired=bool(row.retired),
        retired_date=row.retired_date or '',
        ingrained_discipline_flaw=bool(row.ingrained_discipline_flaw),
        ingrained_discipline_name=row.ingrained_discipline_name or '',
        ingrained_discipline_xp_used=row.ingrained_discipline_xp_used or 0,
    )


def _row_to_period(row: DbPlayPeriod) -> PlayPeriod:
    return PlayPeriod(
        period_label=row.period_label,
        night_number=row.night_number or 0,
        start_date=row.start_date or '',
        end_date=row.end_date or '',
        session_number=row.session_number or 0,
        submissions_open=bool(row.submissions_open),
        active=bool(row.active),
        period_type=row.period_type or 'night',
    )


def _row_to_criteria(row: DbCriteria) -> Criteria:
    return Criteria(
        criteria_id=row.id,
        label=row.label or '',
        description=row.description or '',
        xp_value=row.xp_value or 0,
        category=row.category or 'player',
        requires_rp_links=bool(row.requires_rp_links),
        requires_text_note=bool(row.requires_text_note),
        active=bool(row.active),
        sort_order=row.sort_order or 0,
    )


def _row_to_claim(row: DbXPClaim) -> XPClaim:
    return XPClaim(
        row_index=row.id,
        timestamp=row.timestamp or '',
        character_name=row.character_name or '',
        play_period=row.play_period or '',
        claimed_criteria=_jloads(row.claimed_criteria, []),
        rp_links=_jloads(row.rp_links, []),
        path=row.path or 'none',
        helper_note=row.helper_note or '',
        computed_xp=row.computed_xp or 0,
        status=row.status or 'Pending',
        approved_xp=row.approved_xp or 0,
        reviewed_by=row.reviewed_by or '',
        review_date=row.review_date or '',
        st_notes=row.st_notes or '',
        staff_claim_conflict=bool(row.staff_claim_conflict),
    )


def _row_to_spend(row: DbSpendRequest) -> SpendRequest:
    return SpendRequest(
        row_index=row.id,
        timestamp=row.timestamp or '',
        character_name=row.character_name or '',
        spend_category=row.spend_category or '',
        trait_name=row.trait_name or '',
        current_dots=row.current_dots or 0,
        new_dots=row.new_dots or 0,
        xp_cost=row.xp_cost or 0,
        justification=row.justification or '',
        status=row.status or 'Pending',
        verified_cost=row.verified_cost or 0,
        reviewed_by=row.reviewed_by or '',
        review_date=row.review_date or '',
        st_notes=row.st_notes or '',
        is_humanity=bool(row.is_humanity),
        humanity_no_frenzy=bool(row.humanity_no_frenzy),
        humanity_no_stains=bool(row.humanity_no_stains),
        humanity_humane_act=bool(row.humanity_humane_act),
        is_ingrained_discipline=bool(row.is_ingrained_discipline),
    )


def _row_to_ledger(row: DbLedgerEntry) -> LedgerEntry:
    return LedgerEntry(
        row_index=row.id,
        character_name=row.character_name or '',
        date=row.date or '',
        awarded=row.awarded or 0,
        spent=row.spent or 0,
        reason=row.reason or '',
        entered_by=row.entered_by or '',
        timestamp=row.timestamp or '',
    )


def _row_to_coterie(row: DbCoterie, members: list[str] | None = None) -> Coterie:
    return Coterie(
        coterie_id=row.id,
        name=row.name or '',
        description=row.description or '',
        created_at=row.created_at or '',
        created_by=row.created_by or '',
        active=bool(row.active),
        members=members or [],
        chasse=int(row.chasse or 0),
        lien=int(row.lien or 0),
        portillon=int(row.portillon or 0),
    )


def _row_to_site(row: DbHuntingSite, coterie_name: str = '') -> HuntingSite:
    return HuntingSite(
        site_id=row.id,
        name=row.name or '',
        borough=row.borough or '',
        predator_types=_jloads(row.predator_types, []),
        bonus=row.bonus or '',
        coterie_id=row.coterie_id,
        coterie_name=coterie_name,
        active=bool(row.active),
        sort_order=int(row.sort_order or 0),
    )


# ── DBService ─────────────────────────────────────────────────────────────────

class DBService:

    def __init__(self, sheets_client=None):
        self._sheets = sheets_client

    # ── Criteria (XP earn rules) ──────────────────────────────────────────────

    def seed_criteria_if_empty(self) -> int:
        """Populate the criteria table from NYBN_SEED_CRITERIA if it has no rows.

        Safe to call on every startup — does nothing if criteria already exist.
        Returns the number of rows inserted (0 if already seeded).
        """
        if DbCriteria.query.count() > 0:
            return 0
        for c in NYBN_SEED_CRITERIA:
            row = DbCriteria(
                label=c['label'],
                description=c['description'],
                xp_value=c['xp_value'],
                category=c['category'],
                requires_rp_links=c['requires_rp_links'],
                requires_text_note=c['requires_text_note'],
                active=c['active'],
                sort_order=c['sort_order'],
            )
            db.session.add(row)
        db.session.commit()
        return len(NYBN_SEED_CRITERIA)

    def get_active_criteria(self) -> list[Criteria]:
        rows = DbCriteria.query.filter_by(active=True).order_by(DbCriteria.sort_order).all()
        return [_row_to_criteria(r) for r in rows]

    def get_all_criteria(self) -> list[Criteria]:
        rows = DbCriteria.query.order_by(DbCriteria.sort_order, DbCriteria.id).all()
        return [_row_to_criteria(r) for r in rows]

    def get_criterion(self, criteria_id: int) -> Optional[Criteria]:
        row = DbCriteria.query.get(criteria_id)
        return _row_to_criteria(row) if row else None

    def add_criterion(self, label: str, description: str, xp_value: int,
                      category: str, requires_rp_links: bool,
                      requires_text_note: bool, sort_order: int) -> Criteria:
        row = DbCriteria(
            label=label,
            description=description,
            xp_value=xp_value,
            category=category,
            requires_rp_links=requires_rp_links,
            requires_text_note=requires_text_note,
            active=True,
            sort_order=sort_order,
        )
        db.session.add(row)
        db.session.commit()
        return _row_to_criteria(row)

    def update_criterion(self, criteria_id: int, updates: dict) -> None:
        """Update fields on a criterion. Only affects future submissions."""
        row = DbCriteria.query.get(criteria_id)
        if not row:
            raise ValueError(f'Criterion not found: {criteria_id}')
        allowed = {'label', 'description', 'xp_value', 'category',
                   'requires_rp_links', 'requires_text_note', 'sort_order', 'active'}
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key in ('requires_rp_links', 'requires_text_note', 'active'):
                setattr(row, key, bool(value))
            elif key in ('xp_value', 'sort_order'):
                setattr(row, key, int(value))
            else:
                setattr(row, key, str(value))
        db.session.commit()

    def toggle_criterion(self, criteria_id: int) -> bool:
        """Flip active/inactive. Returns new active state."""
        row = DbCriteria.query.get(criteria_id)
        if not row:
            raise ValueError(f'Criterion not found: {criteria_id}')
        row.active = not row.active
        db.session.commit()
        return bool(row.active)

    def remove_criterion(self, criteria_id: int) -> None:
        """Hard-delete the criterion row. Historical claims reference criteria by id in
        JSON so they remain readable; the label simply won't resolve to a live row."""
        row = DbCriteria.query.get(criteria_id)
        if not row:
            raise ValueError(f'Criterion not found: {criteria_id}')
        db.session.delete(row)
        db.session.commit()

    # ── Roster ────────────────────────────────────────────────────────────────

    def get_all_characters(self) -> list[Character]:
        rows = DbCharacter.query.all()
        return [_row_to_character(r) for r in rows]

    def get_active_characters(self) -> list[Character]:
        rows = DbCharacter.query.filter_by(active=True).all()
        return [_row_to_character(r) for r in rows]

    def get_character(self, name: str) -> Optional[Character]:
        row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == name.lower()
        ).first()
        return _row_to_character(row) if row else None

    def add_character(self, char: Character) -> None:
        row = DbCharacter(
            character_name=char.character_name,
            player_discord=char.player_discord or '',
            player_discord_name=char.player_discord_name or '',
            clan=char.clan or '',
            age_category=char.age_category or '',
            sect=char.sect or '',
            active=char.active,
            creation_xp=char.creation_xp or 0,
            enemy=char.enemy or '',
            date_added=char.date_added or _today_str(),
            notes=char.notes or '',
        )
        db.session.add(row)
        db.session.commit()

    def update_character(self, name: str, updates: dict) -> None:
        row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == name.lower()
        ).first()
        if not row:
            raise ValueError(f'Character not found: {name}')

        bool_fields = {
            'active', 'xp_cap_reached', 'retired',
            'ingrained_discipline_flaw',
        }
        int_fields = {'creation_xp', 'ingrained_discipline_xp_used'}

        for key, value in updates.items():
            if not hasattr(row, key):
                continue
            if key in bool_fields:
                if isinstance(value, str):
                    setattr(row, key, value.strip().upper() in ('TRUE', 'YES', '1'))
                else:
                    setattr(row, key, bool(value))
            elif key in int_fields:
                try:
                    setattr(row, key, int(value))
                except (TypeError, ValueError):
                    setattr(row, key, 0)
            else:
                setattr(row, key, str(value) if value is not None else '')

        db.session.commit()

    def get_characters_by_discord_id(self, discord_id: str) -> list[Character]:
        rows = DbCharacter.query.filter_by(player_discord=str(discord_id)).all()
        return [_row_to_character(r) for r in rows]

    def get_unlinked_characters(self) -> list[Character]:
        rows = DbCharacter.query.filter(
            DbCharacter.active == True,  # noqa: E712
            (DbCharacter.player_discord == None) | (DbCharacter.player_discord == ''),  # noqa: E711
        ).all()
        return [_row_to_character(r) for r in rows]

    def link_character_to_discord(self, character_name: str, discord_id: str,
                                  discord_name: str) -> None:
        self.update_character(character_name, {
            'player_discord': discord_id,
            'player_discord_name': discord_name,
        })

    # ── Player Profiles ───────────────────────────────────────────────────────

    def get_player_profile(self, discord_id: str) -> Optional[PlayerProfile]:
        """Return the PlayerProfile for a Discord user, or None if not found."""
        row = DbPlayerProfile.query.get(str(discord_id))
        if not row:
            return None
        return PlayerProfile(
            discord_id=row.discord_id,
            cubby_channel_id=row.cubby_channel_id or '',
            registered_at=row.registered_at or '',
        )

    def save_player_profile(self, discord_id: str, cubby_channel_id: str) -> PlayerProfile:
        """Create or update a player profile with the given cubby channel ID."""
        row = DbPlayerProfile.query.get(str(discord_id))
        if row:
            row.cubby_channel_id = cubby_channel_id
        else:
            row = DbPlayerProfile(
                discord_id=str(discord_id),
                cubby_channel_id=cubby_channel_id,
                registered_at=_today_str(),
            )
            db.session.add(row)
        db.session.commit()
        return PlayerProfile(
            discord_id=row.discord_id,
            cubby_channel_id=row.cubby_channel_id,
            registered_at=row.registered_at,
        )

    def register_player(self, discord_id: str, discord_name: str,
                        character_name: str, cubby_channel_id: str) -> None:
        """Link a character to a Discord user and store their cubby channel ID.

        Raises ValueError if character not found, not active, or already linked
        to a different Discord ID.
        """
        char = self.get_character(character_name)
        if not char:
            raise ValueError(f'Character "{character_name}" not found.')
        if not char.active:
            raise ValueError(f'"{character_name}" is not an active character.')
        if char.player_discord and char.player_discord != str(discord_id):
            raise ValueError(f'"{character_name}" is already linked to another player.')

        self.link_character_to_discord(character_name, discord_id, discord_name)
        self.save_player_profile(discord_id, cubby_channel_id)

    def deactivate_character(self, name: str) -> None:
        self.update_character(name, {'active': False})

    def delete_character(self, name: str) -> None:
        row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == name.lower()
        ).first()
        if not row:
            raise ValueError(f'Character not found: {name}')
        db.session.delete(row)
        db.session.commit()

    def set_ingrained_discipline_flaw(self, character_name: str,
                                      discipline_name: str) -> None:
        """Grant the Ingrained Discipline Flaw to a character (staff action)."""
        row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == character_name.lower()
        ).first()
        if not row:
            raise ValueError(f'Character not found: {character_name}')
        row.ingrained_discipline_flaw = True
        row.ingrained_discipline_name = discipline_name
        row.ingrained_discipline_xp_used = 0
        db.session.commit()

    def retire_character(self, character_name: str, staff_user: str) -> None:
        """Mark a character as retired."""
        row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == character_name.lower()
        ).first()
        if not row:
            raise ValueError(f'Character not found: {character_name}')
        row.retired = True
        row.retired_date = _today_str()
        row.active = False
        db.session.commit()
        self.log_action(staff_user, 'retire_character', character_name,
                        f'Character retired on {_today_str()}.')

    def unretire_character(self, character_name: str, staff_user: str) -> None:
        """Reverse a retirement — marks the character active again."""
        row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == character_name.lower()
        ).first()
        if not row:
            raise ValueError(f'Character not found: {character_name}')
        row.retired = False
        row.retired_date = ''
        row.active = True
        db.session.commit()
        self.log_action(staff_user, 'unretire_character', character_name,
                        f'Retirement reversed on {_today_str()}.')

    # ── Play Periods ──────────────────────────────────────────────────────────

    def get_all_periods(self) -> list[PlayPeriod]:
        rows = DbPlayPeriod.query.all()
        return [_row_to_period(r) for r in rows]

    def get_active_periods(self) -> list[PlayPeriod]:
        rows = DbPlayPeriod.query.filter_by(active=True).all()
        return [_row_to_period(r) for r in rows]

    def create_period(self, period: PlayPeriod) -> None:
        row = DbPlayPeriod(
            period_label=period.period_label,
            night_number=period.night_number,
            start_date=period.start_date or '',
            end_date=period.end_date or '',
            session_number=period.session_number,
            submissions_open=period.submissions_open,
            active=period.active,
            period_type=getattr(period, 'period_type', 'night') or 'night',
        )
        db.session.add(row)
        db.session.commit()

    def update_period(self, label: str, updates: dict) -> None:
        row = DbPlayPeriod.query.filter_by(period_label=label).first()
        if not row:
            raise ValueError(f'Period not found: {label}')

        bool_fields = {'submissions_open', 'active'}
        for key, value in updates.items():
            if not hasattr(row, key):
                continue
            if key in bool_fields:
                if isinstance(value, str):
                    setattr(row, key, value.strip().upper() in ('TRUE', 'YES', '1'))
                else:
                    setattr(row, key, bool(value))
            elif key in ('night_number', 'session_number'):
                try:
                    setattr(row, key, int(value))
                except (TypeError, ValueError):
                    setattr(row, key, 0)
            else:
                setattr(row, key, str(value) if value is not None else '')

        db.session.commit()

    def get_next_night_number(self) -> int:
        periods = self.get_all_periods()
        if not periods:
            return 1
        nights = [p for p in periods if p.period_type == 'night']
        if not nights:
            return max(p.night_number for p in periods) + 1
        return max(p.night_number for p in nights) + 1

    # ── Chronicle Settings ────────────────────────────────────────────────────

    def get_chronicle_settings(self) -> ChronicleSettings:
        row = DbChronicleSettings.query.get(1)
        if not row:
            return ChronicleSettings()
        return ChronicleSettings(
            server_start_date=row.server_start_date or '2023-04-13',
            timeskip_interval_weeks=row.timeskip_interval_weeks or 8,
            night_duration_days=row.night_duration_days or 12,
            downtime_duration_days=row.downtime_duration_days or 2,
            notes=row.notes or '',
        )

    def save_chronicle_settings(self, settings: ChronicleSettings) -> None:
        row = DbChronicleSettings.query.get(1)
        if not row:
            row = DbChronicleSettings(id=1)
            db.session.add(row)
        row.server_start_date = settings.server_start_date
        row.timeskip_interval_weeks = settings.timeskip_interval_weeks
        row.night_duration_days = settings.night_duration_days
        row.downtime_duration_days = settings.downtime_duration_days
        row.notes = settings.notes
        db.session.commit()

    def seed_chronicle_settings_if_empty(self) -> None:
        """Create the default settings row on first run."""
        if not DbChronicleSettings.query.get(1):
            self.save_chronicle_settings(ChronicleSettings())

    def generate_upcoming_nights(self, count: int = 4) -> list[PlayPeriod]:
        """Generate `count` upcoming nights (plus any required downtime entries)
        starting from the last period in the DB.

        Rules:
        - Nights start on Monday.
        - Each night is `night_duration_days` long.
        - After every (timeskip_interval_weeks // 2) nights, insert a downtime.
        - The downtime is `downtime_duration_days` long, also starting on Monday.
        - Returns the list of PlayPeriod objects that were created.
        """
        from datetime import date as date_cls

        settings = self.get_chronicle_settings()
        night_len = settings.night_duration_days
        dt_len = settings.downtime_duration_days
        nights_per_cycle = max(1, settings.timeskip_interval_weeks // 2)

        all_periods = self.get_all_periods()
        existing_labels = {p.period_label for p in all_periods}

        # Find the latest end date across all existing periods
        def _parse(s: str):
            s = s.replace('-', '')
            if len(s) == 8:
                try:
                    return datetime.strptime(s, '%Y%m%d').date()
                except ValueError:
                    pass
            return None

        last_end: date_cls | None = None
        last_night_num = 0
        nights_since_downtime = 0

        if all_periods:
            for p in sorted(all_periods, key=lambda x: x.night_number):
                ed = _parse(p.end_date)
                if ed and (last_end is None or ed > last_end):
                    last_end = ed
                if p.period_type == 'night':
                    last_night_num = max(last_night_num, p.night_number)
            # Count how many consecutive nights since the last downtime/timeskip
            sorted_periods = sorted(all_periods, key=lambda x: x.night_number)
            for p in reversed(sorted_periods):
                if p.period_type in ('downtime', 'timeskip'):
                    break
                if p.period_type == 'night':
                    nights_since_downtime += 1

        # If no periods exist at all, start at Night 62 the Monday after today
        if last_end is None:
            last_end = date_cls.today()
            last_night_num = 61  # NYbN is on Night 61 currently

        next_night_num = last_night_num + 1
        created: list[PlayPeriod] = []
        nights_generated = 0

        while nights_generated < count:
            # Next start = day after last_end, snapped to Monday
            candidate = last_end + timedelta(days=1)
            while candidate.weekday() != 0:   # 0 = Monday
                candidate += timedelta(days=1)
            next_start = candidate

            # Should we insert a downtime first?
            if nights_since_downtime > 0 and nights_since_downtime % nights_per_cycle == 0:
                # Insert a downtime period
                dt_end = next_start + timedelta(days=dt_len - 1)
                dt_label = f'Downtime — {next_start.strftime("%b %-d") if __import__("sys").platform != "win32" else next_start.strftime("%b %#d")}'
                if dt_label not in existing_labels:
                    dt_period = PlayPeriod(
                        period_label=dt_label,
                        night_number=0,
                        start_date=next_start.strftime('%Y%m%d'),
                        end_date=dt_end.strftime('%Y%m%d'),
                        session_number=0,
                        submissions_open=False,
                        active=True,
                        period_type='downtime',
                    )
                    self.create_period(dt_period)
                    created.append(dt_period)
                    existing_labels.add(dt_label)
                last_end = dt_end
                nights_since_downtime = 0
                continue  # re-loop to place the next night after the downtime

            # Create a regular night
            night_end = next_start + timedelta(days=night_len - 1)
            # Format dates without leading zeros (cross-platform)
            _platform = __import__('sys').platform
            _dfmt = '%#d' if _platform == 'win32' else '%-d'
            start_fmt = next_start.strftime(f'%b {_dfmt}')
            end_fmt = night_end.strftime(f'%b {_dfmt}')
            label = f'Night {next_night_num} - {start_fmt} - {end_fmt}'

            if label not in existing_labels:
                period = PlayPeriod(
                    period_label=label,
                    night_number=next_night_num,
                    start_date=next_start.strftime('%Y%m%d'),
                    end_date=night_end.strftime('%Y%m%d'),
                    session_number=next_night_num,
                    submissions_open=True,
                    active=True,
                    period_type='night',
                )
                self.create_period(period)
                created.append(period)
                existing_labels.add(label)

            last_end = night_end
            last_night_num = next_night_num
            next_night_num += 1
            nights_since_downtime += 1
            nights_generated += 1

        return created

    def auto_create_next_period_if_due(
        self,
        *,
        open_lead_days: int = 1,
        default_length_days: int = 14,
        default_gap_days: int = 0,
        now: Optional[datetime] = None,
    ) -> dict:
        periods = self.get_all_periods()
        if not periods:
            return {'created': False, 'reason': 'no_periods', 'period': None}

        periods.sort(key=lambda p: p.night_number)
        latest = periods[-1]
        next_night = latest.night_number + 1
        if any(p.night_number == next_night for p in periods):
            return {'created': False, 'reason': 'next_already_exists', 'period': None}

        latest_start = _parse_yyyymmdd(latest.start_date)
        latest_end = _parse_yyyymmdd(latest.end_date)
        if not latest_start or not latest_end:
            return {'created': False, 'reason': 'invalid_latest_dates', 'period': None}

        now_dt = now or datetime.now()
        trigger_dt = latest_end - timedelta(days=max(0, int(open_lead_days)))
        if now_dt < trigger_dt:
            return {'created': False, 'reason': 'not_due_yet', 'period': None}

        length_days = max(1, int(default_length_days))
        gap_days = max(0, int(default_gap_days))
        if len(periods) >= 2:
            prev = periods[-2]
            prev_end = _parse_yyyymmdd(prev.end_date)
            inferred_len = (latest_end - latest_start).days
            if inferred_len > 0:
                length_days = inferred_len
            if prev_end:
                inferred_gap = (latest_start - prev_end).days
                if inferred_gap >= 0:
                    gap_days = inferred_gap

        next_start = latest_end + timedelta(days=gap_days)
        next_end = next_start + timedelta(days=length_days)
        next_period = PlayPeriod(
            period_label=f'Night {next_night} - {_short_md(next_start)} - {_short_md(next_end)}',
            night_number=next_night,
            start_date=next_start.strftime('%Y%m%d'),
            end_date=next_end.strftime('%Y%m%d'),
            session_number=next_night,
            submissions_open=True,
            active=True,
        )
        self.create_period(next_period)
        return {'created': True, 'reason': 'created', 'period': next_period}

    def bulk_add_periods(self, periods: list[dict], staff_user: str) -> int:
        existing_nights = {p.night_number for p in self.get_all_periods()}
        added = 0
        for p in periods:
            if p['night'] in existing_nights:
                continue
            label = p.get('label', f"Night {p['night']}")
            if ' - ' not in label and p.get('start') and p.get('end'):
                try:
                    sd = datetime.strptime(p['start'], '%Y%m%d')
                    ed = datetime.strptime(p['end'], '%Y%m%d')
                    label = f"Night {p['night']} - {_short_md(sd)} - {_short_md(ed)}"
                except (ValueError, KeyError):
                    pass
            row = DbPlayPeriod(
                period_label=label,
                night_number=p['night'],
                start_date=p.get('start', ''),
                end_date=p.get('end', ''),
                session_number=p['night'],
                submissions_open=False,
                active=True,
            )
            db.session.add(row)
            existing_nights.add(p['night'])
            added += 1
        if added:
            db.session.commit()
        return added

    # ── XP Claims ─────────────────────────────────────────────────────────────

    def get_all_claims(self) -> list[XPClaim]:
        rows = DbXPClaim.query.order_by(DbXPClaim.id.asc()).all()
        return [_row_to_claim(r) for r in rows]

    def get_pending_claims(self) -> list[XPClaim]:
        rows = DbXPClaim.query.filter(
            func.lower(DbXPClaim.status) == 'pending'
        ).order_by(DbXPClaim.id.asc()).all()
        return [_row_to_claim(r) for r in rows]

    def get_claims_for_character(self, name: str) -> list[XPClaim]:
        rows = DbXPClaim.query.filter(
            func.lower(DbXPClaim.character_name) == name.lower()
        ).order_by(DbXPClaim.id.asc()).all()
        return [_row_to_claim(r) for r in rows]

    def get_claim_by_row(self, row_index: int) -> Optional[XPClaim]:
        row = DbXPClaim.query.get(row_index)
        return _row_to_claim(row) if row else None

    def submit_xp_claim(
        self,
        character_name: str,
        play_period: str,
        claimed_criteria_ids: list[int],
        rp_links: list[str],
        path: str = 'none',
        helper_note: str = '',
    ) -> XPClaim:
        """Submit a new XP earn claim.

        claimed_criteria_ids: list of DbCriteria.id values the player is claiming.
        Values are snapshotted from the criteria table at submission time.

        Raises ValueError if:
        - A non-denied claim already exists for this character + period.
        - The character has hit the XP cap.
        - A criteria_id is not found or not active.
        - Staff/helper path conflicts with no staff role (caller must check role).
        """
        # Block submissions if character is at cap or retired
        char_row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == character_name.lower()
        ).first()
        if char_row and (char_row.xp_cap_reached or char_row.retired):
            raise ValueError(
                f'{character_name} has reached the {XP_CAP} XP cap and cannot '
                f'submit new XP claims. Please retire the character within 6 months.'
            )

        # Duplicate check
        existing = DbXPClaim.query.filter(
            func.lower(DbXPClaim.character_name) == character_name.lower(),
            func.lower(DbXPClaim.play_period) == play_period.lower(),
        ).all()
        for c in existing:
            if (c.status or '').lower() not in ('denied',):
                raise ValueError(
                    f'An XP claim for {character_name} in "{play_period}" '
                    f'already exists (status: {c.status}).'
                )

        # Snapshot criteria values
        snapshot = []
        for cid in claimed_criteria_ids:
            crit_row = DbCriteria.query.get(cid)
            if not crit_row or not crit_row.active:
                raise ValueError(f'Criterion {cid} not found or inactive.')
            snapshot.append({
                'criteria_id': crit_row.id,
                'label': crit_row.label,
                'xp_value_at_submission': crit_row.xp_value,
            })

        computed_xp = sum(s['xp_value_at_submission'] for s in snapshot)

        # Staff/Helper conflict check (same player, same period, another character)
        staff_claim_conflict = False
        if path in ('staff', 'helper') and char_row and char_row.player_discord:
            other_chars = DbCharacter.query.filter(
                DbCharacter.player_discord == char_row.player_discord,
                func.lower(DbCharacter.character_name) != character_name.lower(),
            ).all()
            for other in other_chars:
                conflict_claim = DbXPClaim.query.filter(
                    func.lower(DbXPClaim.character_name) == other.character_name.lower(),
                    func.lower(DbXPClaim.play_period) == play_period.lower(),
                    DbXPClaim.path.in_(('staff', 'helper')),
                    DbXPClaim.status != 'Denied',
                ).first()
                if conflict_claim:
                    staff_claim_conflict = True
                    break

        row = DbXPClaim(
            timestamp=_now_str(),
            character_name=character_name,
            play_period=play_period,
            claimed_criteria=json.dumps(snapshot),
            rp_links=json.dumps([u for u in rp_links if u]),
            path=path,
            helper_note=helper_note,
            computed_xp=computed_xp,
            status='Pending',
            approved_xp=0,
            staff_claim_conflict=staff_claim_conflict,
        )
        db.session.add(row)
        db.session.commit()
        return _row_to_claim(row)

    def approve_claim(self, row_index: int, approved_xp: int,
                      reviewer: str, notes: str = '') -> dict:
        """Approve an XP claim. Creates a ledger entry and checks XP cap.

        Returns dict with keys: approved, cap_reached, cap_message.
        """
        row = DbXPClaim.query.get(row_index)
        if not row:
            raise ValueError(f'Claim not found: {row_index}')
        row.status = 'Approved'
        row.approved_xp = approved_xp
        row.reviewed_by = reviewer
        row.review_date = _now_str()
        row.st_notes = notes

        # Create ledger entry so XP totals stay current
        ledger_row = DbLedgerEntry(
            character_name=row.character_name,
            date=_today_str(),
            awarded=approved_xp,
            spent=0,
            reason=f'XP claim approved — {row.play_period}',
            entered_by=reviewer,
            timestamp=_now_str(),
        )
        db.session.add(ledger_row)
        db.session.commit()

        # XP cap check
        return self._check_and_apply_xp_cap(row.character_name, reviewer)

    def deny_claim(self, row_index: int, reviewer: str, notes: str = '') -> None:
        row = DbXPClaim.query.get(row_index)
        if not row:
            raise ValueError(f'Claim not found: {row_index}')
        row.status = 'Denied'
        row.approved_xp = 0
        row.reviewed_by = reviewer
        row.review_date = _now_str()
        row.st_notes = notes
        db.session.commit()

    # ── Spend Requests ────────────────────────────────────────────────────────

    def get_all_spends(self) -> list[SpendRequest]:
        rows = DbSpendRequest.query.order_by(DbSpendRequest.id.asc()).all()
        return [_row_to_spend(r) for r in rows]

    def get_pending_spends(self) -> list[SpendRequest]:
        rows = DbSpendRequest.query.filter(
            func.lower(DbSpendRequest.status) == 'pending'
        ).order_by(DbSpendRequest.id.asc()).all()
        return [_row_to_spend(r) for r in rows]

    def get_pending_coterie_spends_count(self) -> int:
        """Count coterie spends in 'Funded' state — fully committed, awaiting staff approval."""
        return DbCoterieSpend.query.filter(
            func.lower(DbCoterieSpend.status) == 'funded'
        ).count()

    def get_night_status(self) -> dict:
        """Return current open night period info for the dashboard night-status card."""
        from datetime import date as date_cls
        open_period = DbPlayPeriod.query.filter_by(
            submissions_open=True, active=True, period_type='night'
        ).order_by(DbPlayPeriod.night_number.desc()).first()

        if not open_period:
            return {
                'has_open_night': False,
                'night_number': 0,
                'period_label': '',
                'start_date': '',
                'end_date': '',
                'days_remaining': 0,
                'submissions_open': False,
                'night_xp_total': 0,
            }

        days_remaining = 0
        try:
            # Dates stored as YYYYMMDD
            ed = datetime.strptime(open_period.end_date, '%Y%m%d').date()
            days_remaining = max(0, (ed - date_cls.today()).days)
        except (ValueError, TypeError):
            pass

        # XP approved for this period's claims
        xp_total = db.session.query(
            func.coalesce(func.sum(DbXPClaim.approved_xp), 0)
        ).filter(
            DbXPClaim.play_period == open_period.period_label,
            func.lower(DbXPClaim.status) == 'approved',
        ).scalar()

        return {
            'has_open_night': True,
            'night_number': open_period.night_number,
            'period_label': open_period.period_label,
            'start_date': open_period.start_date,
            'end_date': open_period.end_date,
            'days_remaining': days_remaining,
            'submissions_open': bool(open_period.submissions_open),
            'night_xp_total': int(xp_total or 0),
        }

    def get_spends_for_character(self, name: str) -> list[SpendRequest]:
        rows = DbSpendRequest.query.filter(
            func.lower(DbSpendRequest.character_name) == name.lower()
        ).order_by(DbSpendRequest.id.asc()).all()
        return [_row_to_spend(r) for r in rows]

    def get_spend_by_row(self, row_index: int) -> Optional[SpendRequest]:
        row = DbSpendRequest.query.get(row_index)
        return _row_to_spend(row) if row else None

    def submit_spend_request(
        self,
        character_name: str,
        spend_category: str,
        trait_name: str,
        current_dots: int,
        new_dots: int,
        justification: str,
        *,
        humanity_no_frenzy: bool = False,
        humanity_no_stains: bool = False,
        humanity_humane_act: bool = False,
    ) -> int:
        """Submit a new spend request. Returns the calculated XP cost.

        For Humanity: all three condition flags must be True.
        For Ingrained Discipline: validates the 15 XP flaw budget.
        Raises ValueError if validation fails.
        """
        from app.xp_rules import calculate_xp_cost, XP_COSTS

        is_humanity = spend_category == 'Humanity'
        is_ingrained = spend_category == 'Ingrained Discipline'

        # Humanity condition enforcement
        if is_humanity:
            if new_dots != current_dots + 1:
                raise ValueError('Humanity can only be purchased one dot at a time.')
            if not (humanity_no_frenzy and humanity_no_stains and humanity_humane_act):
                raise ValueError(
                    'All three Humanity conditions must be certified before submitting.'
                )

        # Ingrained Discipline flaw budget check
        if is_ingrained:
            char_row = DbCharacter.query.filter(
                func.lower(DbCharacter.character_name) == character_name.lower()
            ).first()
            if not char_row or not char_row.ingrained_discipline_flaw:
                raise ValueError(
                    f'{character_name} does not have the Ingrained Discipline Flaw.'
                )
            flaw_cap = XP_COSTS.get('Ingrained Discipline', {}).get('flaw_xp_cap', 15)
            xp_cost = calculate_xp_cost('Ingrained Discipline', current_dots, new_dots)
            used = char_row.ingrained_discipline_xp_used or 0
            if used + xp_cost > flaw_cap:
                remaining = flaw_cap - used
                raise ValueError(
                    f'This spend ({xp_cost} XP) would exceed the Ingrained Discipline '
                    f'budget. Remaining: {remaining} XP.'
                )
        else:
            xp_cost = calculate_xp_cost(spend_category, current_dots, new_dots)

        row = DbSpendRequest(
            timestamp=_now_str(),
            character_name=character_name,
            spend_category=spend_category,
            trait_name=trait_name,
            current_dots=current_dots,
            new_dots=new_dots,
            xp_cost=xp_cost,
            justification=justification,
            status='Pending',
            verified_cost=0,
            is_humanity=is_humanity,
            humanity_no_frenzy=humanity_no_frenzy,
            humanity_no_stains=humanity_no_stains,
            humanity_humane_act=humanity_humane_act,
            is_ingrained_discipline=is_ingrained,
        )
        db.session.add(row)
        db.session.commit()
        return xp_cost

    def approve_spend(self, row_index: int, verified_cost: int,
                      reviewer: str, notes: str = '') -> None:
        """Approve a spend request. Creates a ledger entry and updates Ingrained
        Discipline budget if applicable."""
        row = DbSpendRequest.query.get(row_index)
        if not row:
            raise ValueError(f'Spend request not found: {row_index}')
        row.status = 'Approved'
        row.verified_cost = verified_cost
        row.reviewed_by = reviewer
        row.review_date = _now_str()
        row.st_notes = notes

        # Create ledger entry
        ledger_row = DbLedgerEntry(
            character_name=row.character_name,
            date=_today_str(),
            awarded=0,
            spent=verified_cost,
            reason=f'{row.spend_category}: {row.trait_name} ({row.current_dots}→{row.new_dots})',
            entered_by=reviewer,
            timestamp=_now_str(),
        )
        db.session.add(ledger_row)

        # Track Ingrained Discipline budget
        if row.is_ingrained_discipline:
            char_row = DbCharacter.query.filter(
                func.lower(DbCharacter.character_name) == row.character_name.lower()
            ).first()
            if char_row:
                char_row.ingrained_discipline_xp_used = (
                    (char_row.ingrained_discipline_xp_used or 0) + verified_cost
                )

        db.session.commit()

    def deny_spend(self, row_index: int, reviewer: str, notes: str = '') -> None:
        row = DbSpendRequest.query.get(row_index)
        if not row:
            raise ValueError(f'Spend request not found: {row_index}')
        row.status = 'Denied'
        row.verified_cost = 0
        row.reviewed_by = reviewer
        row.review_date = _now_str()
        row.st_notes = notes
        db.session.commit()

    # ── XP Cap ────────────────────────────────────────────────────────────────

    def _check_and_apply_xp_cap(self, character_name: str,
                                 staff_user: str) -> dict:
        """Check total earned XP against XP_CAP. If cap is newly reached, sets
        cap fields and opens the 6-month retirement window.

        Returns dict: {cap_reached: bool, cap_message: str | None}
        """
        char_row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == character_name.lower()
        ).first()
        if not char_row or char_row.xp_cap_reached:
            return {'cap_reached': False, 'cap_message': None}

        totals = self.get_xp_totals(character_name)
        total_earned = totals.get('total_xp', 0)

        if total_earned < XP_CAP:
            return {'cap_reached': False, 'cap_message': None}

        # Cap reached — set the retirement window
        today = _today_str()
        retirement_deadline = (datetime.utcnow() + timedelta(days=183)).strftime('%Y-%m-%d')
        char_row.xp_cap_reached = True
        char_row.xp_cap_reached_date = today
        char_row.retirement_deadline = retirement_deadline
        db.session.commit()

        self.log_action(
            staff_user, 'xp_cap_reached', character_name,
            f'{character_name} reached {XP_CAP} XP on {today}. '
            f'Retirement deadline: {retirement_deadline}.'
        )

        msg = (
            f'🏆 {character_name} has reached the {XP_CAP} XP cap! '
            f'They have until {retirement_deadline} to wrap up their story.'
        )
        return {'cap_reached': True, 'cap_message': msg}

    def get_characters_near_cap(self, threshold: int = 30) -> list[dict]:
        """Return active characters within `threshold` XP of the cap, not yet capped."""
        chars = DbCharacter.query.filter_by(active=True, xp_cap_reached=False).all()
        result = []
        for char in chars:
            totals = self.get_xp_totals(char.character_name)
            total = totals.get('total_xp', 0)
            if XP_CAP - total <= threshold:
                result.append({
                    'character_name': char.character_name,
                    'total_xp': total,
                    'xp_to_cap': XP_CAP - total,
                })
        result.sort(key=lambda r: r['xp_to_cap'])
        return result

    # ── XP Totals ─────────────────────────────────────────────────────────────

    def get_xp_totals(self, name: str) -> dict:
        char_row = DbCharacter.query.filter(
            func.lower(DbCharacter.character_name) == name.lower()
        ).first()
        creation_xp = char_row.creation_xp or 0 if char_row else 0

        spend_result = db.session.query(
            func.coalesce(func.sum(DbSpendRequest.verified_cost), 0)
        ).filter(
            func.lower(DbSpendRequest.character_name) == name.lower(),
            func.lower(DbSpendRequest.status) == 'approved',
        ).scalar()
        total_spends = int(spend_result or 0)

        ledger_result = db.session.query(
            func.coalesce(func.sum(DbLedgerEntry.awarded), 0).label('awarded'),
            func.coalesce(func.sum(DbLedgerEntry.spent), 0).label('spent'),
        ).filter(
            func.lower(DbLedgerEntry.character_name) == name.lower()
        ).first()
        ledger_awarded = int(ledger_result.awarded or 0)
        ledger_spent = int(ledger_result.spent or 0)

        total_xp = creation_xp + ledger_awarded
        available_xp = total_xp - total_spends - ledger_spent

        return {
            'creation_xp': creation_xp,
            'earned_xp': ledger_awarded,
            'total_spends': total_spends,
            'ledger_awarded': ledger_awarded,
            'ledger_spent': ledger_spent,
            'total_xp': total_xp,
            'available_xp': available_xp,
            'xp_to_cap': max(0, XP_CAP - total_xp),
            'cap_reached': bool(char_row and char_row.xp_cap_reached) if char_row else False,
        }

    def get_dashboard_data(self) -> list[dict]:
        characters = DbCharacter.query.all()

        # Determine the current open night for the "no claim this period" filter
        open_period = DbPlayPeriod.query.filter_by(
            submissions_open=True, active=True, period_type='night'
        ).order_by(DbPlayPeriod.night_number.desc()).first()
        current_period_label = open_period.period_label if open_period else None

        if current_period_label:
            claimed_this_period: set[str] = {
                r[0].lower() for r in
                db.session.query(func.lower(DbXPClaim.character_name)).filter(
                    DbXPClaim.play_period == current_period_label,
                    func.lower(DbXPClaim.status) != 'denied',
                ).all()
            }
        else:
            claimed_this_period = set()

        ledger_agg = db.session.query(
            func.lower(DbLedgerEntry.character_name).label('name_lower'),
            func.coalesce(func.sum(DbLedgerEntry.awarded), 0).label('earned_xp'),
            func.coalesce(func.sum(DbLedgerEntry.spent), 0).label('ledger_spent'),
            func.max(DbLedgerEntry.timestamp).label('last_submission'),
        ).group_by(func.lower(DbLedgerEntry.character_name)).all()

        ledger_by_name: dict[str, dict] = {}
        for row in ledger_agg:
            ledger_by_name[row.name_lower] = {
                'earned_xp': int(row.earned_xp or 0),
                'ledger_spent': int(row.ledger_spent or 0),
                'last_submission': row.last_submission or '',
            }

        spend_agg = db.session.query(
            func.lower(DbSpendRequest.character_name).label('name_lower'),
            func.coalesce(func.sum(DbSpendRequest.verified_cost), 0).label('total_spends'),
        ).filter(
            func.lower(DbSpendRequest.status) == 'approved'
        ).group_by(func.lower(DbSpendRequest.character_name)).all()

        spend_by_name: dict[str, int] = {}
        for row in spend_agg:
            spend_by_name[row.name_lower] = int(row.total_spends or 0)

        result = []
        for char in characters:
            name_lower = char.character_name.lower()
            ledger_data = ledger_by_name.get(name_lower, {
                'earned_xp': 0, 'ledger_spent': 0, 'last_submission': ''
            })
            earned_xp = ledger_data['earned_xp']
            ledger_spent = ledger_data['ledger_spent']
            last_submission = ledger_data['last_submission']

            total_spends = spend_by_name.get(name_lower, 0)
            creation_xp = char.creation_xp or 0
            total_xp = creation_xp + earned_xp
            available_xp = total_xp - total_spends - ledger_spent

            result.append({
                'character_name': char.character_name,
                'player_discord': char.player_discord or '',
                'clan': char.clan or '',
                'active': bool(char.active),
                'creation_xp': creation_xp,
                'earned_xp': earned_xp,
                'total_xp': total_xp,
                'approved_spends': total_spends + ledger_spent,
                'available_xp': available_xp,
                'last_submission': last_submission,
                'xp_to_cap': max(0, XP_CAP - total_xp),
                'xp_cap_reached': bool(char.xp_cap_reached),
                'retired': bool(char.retired),
                'retirement_deadline': char.retirement_deadline or '',
                'no_claim_this_period': bool(
                    char.active and current_period_label
                    and name_lower not in claimed_this_period
                ),
            })

        result.sort(key=lambda r: (not r['active'], r['character_name']))
        return result

    # ── XP Ledger ─────────────────────────────────────────────────────────────

    def get_ledger_for_character(self, name: str) -> list[LedgerEntry]:
        rows = DbLedgerEntry.query.filter(
            func.lower(DbLedgerEntry.character_name) == name.lower()
        ).all()
        entries = [_row_to_ledger(r) for r in rows]
        entries.sort(key=lambda e: e.date, reverse=True)
        return entries

    def add_ledger_entry(self, character_name: str, date: str,
                         awarded: int, spent: int, reason: str,
                         staff_user: str) -> None:
        row = DbLedgerEntry(
            character_name=character_name,
            date=date,
            awarded=awarded,
            spent=spent,
            reason=reason,
            entered_by=staff_user,
            timestamp=_now_str(),
        )
        db.session.add(row)
        db.session.commit()

    def delete_ledger_entry(self, row_index: int) -> None:
        row = DbLedgerEntry.query.get(row_index)
        if not row:
            raise ValueError(f'Ledger entry not found: {row_index}')
        db.session.delete(row)
        db.session.commit()

    def bulk_add_ledger_entries(self, character_name: str,
                                entries: list[dict],
                                staff_user: str) -> int:
        now = _now_str()
        rows = []
        for e in entries:
            rows.append(DbLedgerEntry(
                character_name=character_name,
                date=e['date'],
                awarded=e.get('awarded', 0),
                spent=e.get('spent', 0),
                reason=e.get('reason', ''),
                entered_by=staff_user,
                timestamp=now,
            ))
        if rows:
            db.session.add_all(rows)
            db.session.commit()
        return len(rows)

    def preview_ledger_import(self, spreadsheet_url: str) -> list[dict]:
        if self._sheets is None:
            raise RuntimeError('Sheets client required for import preview')
        return self._sheets.preview_ledger_import(spreadsheet_url)

    def preview_period_import(self, spreadsheet_url: str) -> list[dict]:
        if self._sheets is None:
            raise RuntimeError('Sheets client required for import preview')
        return self._sheets.preview_period_import(spreadsheet_url)

    # ── Coteries ──────────────────────────────────────────────────────────────

    def get_all_coteries(self) -> list[Coterie]:
        rows = DbCoterie.query.order_by(DbCoterie.name).all()
        result = []
        for row in rows:
            members = [
                m.character_name for m in
                DbCoterieMembership.query.filter_by(coterie_id=row.id).all()
            ]
            result.append(_row_to_coterie(row, members))
        return result

    def get_coterie(self, coterie_id: int) -> Optional[Coterie]:
        row = DbCoterie.query.get(coterie_id)
        if not row:
            return None
        members = [
            m.character_name for m in
            DbCoterieMembership.query.filter_by(coterie_id=row.id).all()
        ]
        return _row_to_coterie(row, members)

    def get_coterie_for_character(self, character_name: str) -> Optional[Coterie]:
        membership = DbCoterieMembership.query.filter(
            func.lower(DbCoterieMembership.character_name) == character_name.lower()
        ).first()
        if not membership:
            return None
        return self.get_coterie(membership.coterie_id)

    def create_coterie(self, name: str, description: str,
                       staff_user: str) -> Coterie:
        if DbCoterie.query.filter(
            func.lower(DbCoterie.name) == name.lower()
        ).first():
            raise ValueError(f'A coterie named "{name}" already exists.')
        row = DbCoterie(
            name=name,
            description=description,
            created_at=_today_str(),
            created_by=staff_user,
            active=True,
        )
        db.session.add(row)
        db.session.commit()
        self.log_action(staff_user, 'create_coterie', name,
                        f'Coterie "{name}" created.')
        return _row_to_coterie(row, [])

    def add_coterie_member(self, coterie_id: int,
                           character_name: str, staff_user: str) -> None:
        coterie = DbCoterie.query.get(coterie_id)
        if not coterie:
            raise ValueError(f'Coterie {coterie_id} not found.')

        current_count = DbCoterieMembership.query.filter_by(coterie_id=coterie_id).count()
        if current_count >= COTERIE_MAX_MEMBERS:
            raise ValueError(
                f'Coterie "{coterie.name}" is full ({COTERIE_MAX_MEMBERS} members max).'
            )

        # Check not already in a coterie
        existing = DbCoterieMembership.query.filter(
            func.lower(DbCoterieMembership.character_name) == character_name.lower()
        ).first()
        if existing:
            other = DbCoterie.query.get(existing.coterie_id)
            raise ValueError(
                f'{character_name} is already in coterie '
                f'"{other.name if other else existing.coterie_id}".'
            )

        member = DbCoterieMembership(
            coterie_id=coterie_id,
            character_name=character_name,
            joined_at=_today_str(),
        )
        db.session.add(member)
        db.session.commit()
        self.log_action(staff_user, 'add_coterie_member', character_name,
                        f'Added to coterie "{coterie.name}".')

    def remove_coterie_member(self, coterie_id: int,
                              character_name: str, staff_user: str) -> None:
        member = DbCoterieMembership.query.filter(
            DbCoterieMembership.coterie_id == coterie_id,
            func.lower(DbCoterieMembership.character_name) == character_name.lower(),
        ).first()
        if not member:
            raise ValueError(f'{character_name} is not in coterie {coterie_id}.')
        db.session.delete(member)
        db.session.commit()
        coterie = DbCoterie.query.get(coterie_id)
        self.log_action(staff_user, 'remove_coterie_member', character_name,
                        f'Removed from coterie "{coterie.name if coterie else coterie_id}".')

    def submit_coterie_spend(
        self,
        coterie_id: int,
        initiated_by: str,
        spend_category: str,
        trait_name: str,
        xp_cost_per_member: int,
        justification: str,
    ) -> CoterieSpend:
        """Initiate a coterie group spend. Each member must then commit their share.

        total_xp_cost = xp_cost_per_member × number of active members.
        """
        from app.xp_rules import calculate_xp_cost  # noqa: F401 (future validation)

        coterie = DbCoterie.query.get(coterie_id)
        if not coterie:
            raise ValueError(f'Coterie {coterie_id} not found.')

        members = DbCoterieMembership.query.filter_by(coterie_id=coterie_id).all()
        member_count = len(members)
        if member_count == 0:
            raise ValueError('Coterie has no members.')

        total_xp = xp_cost_per_member * member_count

        row = DbCoterieSpend(
            coterie_id=coterie_id,
            initiated_by=initiated_by,
            spend_category=spend_category,
            trait_name=trait_name,
            xp_cost_per_member=xp_cost_per_member,
            total_xp_cost=total_xp,
            contributions=json.dumps({}),
            status='Pending',
            justification=justification,
            timestamp=_now_str(),
        )
        db.session.add(row)
        db.session.commit()

        spend = CoterieSpend(
            coterie_id=coterie_id,
            coterie_name=coterie.name,
            initiated_by=initiated_by,
            spend_category=spend_category,
            trait_name=trait_name,
            xp_cost_per_member=xp_cost_per_member,
            total_xp_cost=total_xp,
            status='Pending',
            justification=justification,
        )
        return spend

    def commit_coterie_contribution(self, coterie_spend_id: int,
                                    character_name: str) -> dict:
        """Record that a member has committed their XP share.

        When all members have committed, status moves to Funded (ready for staff approval).
        Returns {status, all_committed, members_remaining}.
        """
        row = DbCoterieSpend.query.get(coterie_spend_id)
        if not row:
            raise ValueError(f'Coterie spend {coterie_spend_id} not found.')
        if row.status not in ('Pending',):
            raise ValueError(f'Coterie spend is already {row.status}.')

        contributions = _jloads(row.contributions, {})
        contributions[character_name] = row.xp_cost_per_member
        row.contributions = json.dumps(contributions)

        members = DbCoterieMembership.query.filter_by(coterie_id=row.coterie_id).all()
        all_names = {m.character_name.lower() for m in members}
        committed = {n.lower() for n in contributions}
        remaining = all_names - committed

        if not remaining:
            row.status = 'Funded'

        db.session.commit()
        return {
            'status': row.status,
            'all_committed': not remaining,
            'members_remaining': list(remaining),
        }

    def approve_coterie_spend(self, coterie_spend_id: int,
                              reviewer: str, notes: str = '') -> None:
        """Approve a funded coterie spend. Creates ledger entries for all members."""
        row = DbCoterieSpend.query.get(coterie_spend_id)
        if not row:
            raise ValueError(f'Coterie spend {coterie_spend_id} not found.')
        if row.status != 'Funded':
            raise ValueError(f'Coterie spend must be Funded before approval (is: {row.status}).')

        row.status = 'Approved'
        row.reviewed_by = reviewer
        row.review_date = _now_str()
        row.st_notes = notes

        contributions = _jloads(row.contributions, {})
        coterie = DbCoterie.query.get(row.coterie_id)
        coterie_name = coterie.name if coterie else str(row.coterie_id)

        now = _now_str()
        today = _today_str()
        for char_name, xp_amount in contributions.items():
            ledger_row = DbLedgerEntry(
                character_name=char_name,
                date=today,
                awarded=0,
                spent=int(xp_amount),
                reason=f'Coterie spend ({coterie_name}): {row.spend_category} — {row.trait_name}',
                entered_by=reviewer,
                timestamp=now,
            )
            db.session.add(ledger_row)

        db.session.commit()

    def deny_coterie_spend(self, coterie_spend_id: int,
                           reviewer: str, notes: str = '') -> None:
        row = DbCoterieSpend.query.get(coterie_spend_id)
        if not row:
            raise ValueError(f'Coterie spend {coterie_spend_id} not found.')
        row.status = 'Denied'
        row.reviewed_by = reviewer
        row.review_date = _now_str()
        row.st_notes = notes
        db.session.commit()

    def get_coterie_spends(self, coterie_id: int) -> list[dict]:
        rows = DbCoterieSpend.query.filter_by(coterie_id=coterie_id).order_by(
            DbCoterieSpend.id.desc()
        ).all()
        return [
            {
                'id': r.id,
                'initiated_by': r.initiated_by,
                'spend_category': r.spend_category,
                'trait_name': r.trait_name,
                'xp_cost_per_member': r.xp_cost_per_member,
                'total_xp_cost': r.total_xp_cost,
                'contributions': _jloads(r.contributions, {}),
                'status': r.status,
                'justification': r.justification,
                'reviewed_by': r.reviewed_by,
                'st_notes': r.st_notes,
                'timestamp': r.timestamp,
            }
            for r in rows
        ]

    # ── Coterie ratings ───────────────────────────────────────────────────────

    def update_coterie_ratings(self, coterie_id: int, chasse: int, lien: int,
                                portillon: int, staff_user: str) -> None:
        row = DbCoterie.query.get(coterie_id)
        if not row:
            raise ValueError(f'Coterie {coterie_id} not found.')
        if not (0 <= chasse <= 5 and 0 <= lien <= 5 and 0 <= portillon <= 5):
            raise ValueError('All ratings must be between 0 and 5.')
        if portillon > chasse:
            raise ValueError(f'Portillon ({portillon}) cannot exceed Chasse ({chasse}).')
        row.chasse = chasse
        row.lien = lien
        row.portillon = portillon
        db.session.commit()
        self.log_action(staff_user, 'update_coterie_ratings', row.name,
                        f'Chasse {chasse} / Lien {lien} / Portillon {portillon}')

    # ── Hunting sites ─────────────────────────────────────────────────────────

    def _coterie_name_map(self) -> dict[int, str]:
        return {r.id: r.name for r in DbCoterie.query.all()}

    def get_all_sites(self) -> list[HuntingSite]:
        names = self._coterie_name_map()
        rows = DbHuntingSite.query.order_by(DbHuntingSite.sort_order, DbHuntingSite.name).all()
        return [_row_to_site(r, names.get(r.coterie_id, '')) for r in rows]

    def get_coterie_sites(self, coterie_id: int) -> list[HuntingSite]:
        rows = DbHuntingSite.query.filter_by(coterie_id=coterie_id).order_by(
            DbHuntingSite.sort_order, DbHuntingSite.name
        ).all()
        names = self._coterie_name_map()
        return [_row_to_site(r, names.get(r.coterie_id, '')) for r in rows]

    def assign_site(self, site_id: int, coterie_id: int | None, staff_user: str) -> None:
        row = DbHuntingSite.query.get(site_id)
        if not row:
            raise ValueError(f'Site {site_id} not found.')
        old_coterie = row.coterie_id
        row.coterie_id = coterie_id
        db.session.commit()
        coterie_name = ''
        if coterie_id:
            c = DbCoterie.query.get(coterie_id)
            coterie_name = c.name if c else str(coterie_id)
        self.log_action(staff_user, 'assign_site', row.name,
                        f'Assigned to "{coterie_name}" (was {old_coterie})')

    def seed_sites_if_empty(self) -> None:
        if DbHuntingSite.query.count() > 0:
            return
        for data in NYBN_SEED_SITES:
            import json as _json
            row = DbHuntingSite(
                name=data['name'],
                borough=data['borough'],
                predator_types=_json.dumps(data['predator_types']),
                bonus=data.get('bonus', ''),
                sort_order=data.get('sort_order', 0),
                active=True,
            )
            db.session.add(row)
        db.session.commit()

    # ── Audit Log ─────────────────────────────────────────────────────────────

    def log_action(self, staff_user: str, action_type: str,
                   target: str, details: str) -> None:
        row = DbAuditLog(
            timestamp=_now_str(),
            staff_user=staff_user,
            action_type=action_type,
            target_character=target,
            details=details,
        )
        db.session.add(row)
        db.session.commit()

    def get_audit_log(self, limit: int = 100) -> list[AuditEntry]:
        rows = DbAuditLog.query.order_by(DbAuditLog.id.desc()).limit(limit).all()
        return [
            AuditEntry(
                timestamp=r.timestamp or '',
                staff_user=r.staff_user or '',
                action_type=r.action_type or '',
                target_character=r.target_character or '',
                details=r.details or '',
            )
            for r in rows
        ]
