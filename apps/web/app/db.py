"""SQLAlchemy models for NYbN (New York by Night) XP Tracker."""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Boolean, Text

db = SQLAlchemy()

XP_CAP = 350
COTERIE_MAX_MEMBERS = 6  # NYbN allows 6; MCbN allows 5


class DbCharacter(db.Model):
    __tablename__ = 'characters'
    id = db.Column(Integer, primary_key=True)
    character_name = db.Column(String(200), nullable=False, unique=True, index=True)
    player_discord = db.Column(String(30), default='')
    player_discord_name = db.Column(String(100), default='')
    clan = db.Column(String(50), default='')
    age_category = db.Column(String(50), default='')
    sect = db.Column(String(50), default='')
    active = db.Column(Boolean, default=True, index=True)
    creation_xp = db.Column(Integer, default=0)
    enemy = db.Column(String(200), default='')
    date_added = db.Column(String(20), default='')
    notes = db.Column(Text, default='')

    # XP cap tracking (NYbN cap: 350)
    xp_cap_reached = db.Column(Boolean, default=False, index=True)
    xp_cap_reached_date = db.Column(String(20), default='')   # ISO date cap was hit
    retirement_deadline = db.Column(String(20), default='')   # cap date + 6 months
    retired = db.Column(Boolean, default=False, index=True)
    retired_date = db.Column(String(20), default='')

    # Ingrained Discipline Flaw (up to 15 XP of extra powers, no sheet slot used)
    ingrained_discipline_flaw = db.Column(Boolean, default=False)
    ingrained_discipline_name = db.Column(String(50), default='')  # which Discipline
    ingrained_discipline_xp_used = db.Column(Integer, default=0)   # running total, max 15


class DbPlayPeriod(db.Model):
    __tablename__ = 'play_periods'
    id = db.Column(Integer, primary_key=True)
    period_label = db.Column(String(100), nullable=False, unique=True, index=True)
    night_number = db.Column(Integer, default=0)
    start_date = db.Column(String(10), default='')
    end_date = db.Column(String(10), default='')
    session_number = db.Column(Integer, default=0)
    submissions_open = db.Column(Boolean, default=True)
    active = db.Column(Boolean, default=True)
    # night = regular play period | downtime = short break | timeskip = in-game time jump
    period_type = db.Column(String(20), default='night')


class DbChronicleSettings(db.Model):
    """Singleton row (id=1) — stores chronicle schedule configuration."""
    __tablename__ = 'chronicle_settings'
    id = db.Column(Integer, primary_key=True)
    server_start_date = db.Column(String(10), default='2023-04-13')   # YYYY-MM-DD
    # How many calendar weeks between timeskip/downtime events.
    # Changed from 4 → 8 on 3/16/2026.
    timeskip_interval_weeks = db.Column(Integer, default=8)
    night_duration_days = db.Column(Integer, default=12)   # length of a play night
    downtime_duration_days = db.Column(Integer, default=2) # length of the downtime gap
    notes = db.Column(Text, default='')


class DbCriteria(db.Model):
    """Editable XP earn criteria. The submission form is built from this table.
    Editing a criterion only affects future submissions — past records keep their
    snapshotted values stored in DbXPClaim.claimed_criteria."""
    __tablename__ = 'criteria'
    id = db.Column(Integer, primary_key=True)
    label = db.Column(String(200), nullable=False)
    description = db.Column(Text, default='')
    xp_value = db.Column(Integer, nullable=False, default=0)
    category = db.Column(String(50), default='player')  # base / player / staff / helper
    requires_rp_links = db.Column(Boolean, default=True)
    requires_text_note = db.Column(Boolean, default=False)
    active = db.Column(Boolean, default=True, index=True)
    sort_order = db.Column(Integer, default=0)


class DbXPClaim(db.Model):
    """One XP earn submission per character per play period.

    claimed_criteria stores a JSON snapshot of what was claimed at submission
    time: [{criteria_id, label, xp_value_at_submission}]. This means edits to
    the criteria table never retroactively change approved records.
    """
    __tablename__ = 'xp_claims'
    id = db.Column(Integer, primary_key=True)
    timestamp = db.Column(String(20), default='', index=True)
    character_name = db.Column(String(200), nullable=False, index=True)
    play_period = db.Column(String(100), default='', index=True)

    # Criteria snapshot: JSON list of {criteria_id, label, xp_value_at_submission}
    claimed_criteria = db.Column(Text, default='[]')
    # RP links: JSON list of Discord message URLs
    rp_links = db.Column(Text, default='[]')
    # Staff/Helper path (mutually exclusive)
    path = db.Column(String(20), default='none')   # none / staff / helper
    helper_note = db.Column(Text, default='')       # required when path == helper

    computed_xp = db.Column(Integer, default=0)    # sum of snapshotted values
    status = db.Column(String(20), default='Pending', index=True)
    approved_xp = db.Column(Integer, default=0)
    reviewed_by = db.Column(String(100), default='')
    review_date = db.Column(String(20), default='')
    st_notes = db.Column(Text, default='')

    # Flagged when the same player claimed staff/helper on another character this period
    staff_claim_conflict = db.Column(Boolean, default=False)


class DbSpendRequest(db.Model):
    """An individual XP spend request from a player."""
    __tablename__ = 'spend_requests'
    id = db.Column(Integer, primary_key=True)
    timestamp = db.Column(String(20), default='', index=True)
    character_name = db.Column(String(200), nullable=False, index=True)
    spend_category = db.Column(String(100), default='')
    trait_name = db.Column(String(100), default='')
    current_dots = db.Column(Integer, default=0)
    new_dots = db.Column(Integer, default=0)
    xp_cost = db.Column(Integer, default=0)         # player-submitted cost
    justification = db.Column(Text, default='')
    status = db.Column(String(20), default='Pending', index=True)
    verified_cost = db.Column(Integer, default=0)   # staff-verified cost
    reviewed_by = db.Column(String(100), default='')
    review_date = db.Column(String(20), default='')
    st_notes = db.Column(Text, default='')

    # Humanity conditional spend
    is_humanity = db.Column(Boolean, default=False)
    # Player self-certifies all 4 conditions before submitting
    humanity_no_frenzy = db.Column(Boolean, default=False)
    humanity_no_stains = db.Column(Boolean, default=False)
    humanity_humane_act = db.Column(Boolean, default=False)

    # Ingrained Discipline Flaw spend
    is_ingrained_discipline = db.Column(Boolean, default=False)


class DbLedgerEntry(db.Model):
    """A single line in a character's XP ledger — award or spend."""
    __tablename__ = 'ledger_entries'
    id = db.Column(Integer, primary_key=True)
    character_name = db.Column(String(200), nullable=False, index=True)
    date = db.Column(String(10), default='')
    awarded = db.Column(Integer, default=0)
    spent = db.Column(Integer, default=0)
    reason = db.Column(Text, default='')
    entered_by = db.Column(String(100), default='')
    timestamp = db.Column(String(20), default='')


class DbAuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(Integer, primary_key=True)
    timestamp = db.Column(String(20), default='', index=True)
    staff_user = db.Column(String(100), default='')
    action_type = db.Column(String(100), default='', index=True)
    target_character = db.Column(String(200), default='')
    details = db.Column(Text, default='')


class DbPlayerProfile(db.Model):
    """One row per Discord user — stores cubby channel ID for notifications."""
    __tablename__ = 'player_profiles'
    discord_id = db.Column(String(30), primary_key=True)
    cubby_channel_id = db.Column(String(30), default='')
    registered_at = db.Column(String(20), default='')


# ── Coterie tables ────────────────────────────────────────────────────────────

class DbCoterie(db.Model):
    """A coterie of up to COTERIE_MAX_MEMBERS characters."""
    __tablename__ = 'coteries'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False, unique=True)
    description = db.Column(Text, default='')
    created_at = db.Column(String(20), default='')
    created_by = db.Column(String(100), default='')  # staff Discord ID who created it
    active = db.Column(Boolean, default=True, index=True)
    chasse = db.Column(Integer, default=0)
    lien = db.Column(Integer, default=0)
    portillon = db.Column(Integer, default=0)


class DbCoterieMembership(db.Model):
    """Tracks which characters belong to which coterie."""
    __tablename__ = 'coterie_memberships'
    id = db.Column(Integer, primary_key=True)
    coterie_id = db.Column(Integer, db.ForeignKey('coteries.id'), nullable=False, index=True)
    character_name = db.Column(String(200), nullable=False, index=True)
    joined_at = db.Column(String(20), default='')

    __table_args__ = (
        db.UniqueConstraint('coterie_id', 'character_name', name='uq_coterie_member'),
    )


class DbCoterieSpend(db.Model):
    """A group XP spend where coterie members each contribute XP toward a shared purchase."""
    __tablename__ = 'coterie_spends'
    id = db.Column(Integer, primary_key=True)
    coterie_id = db.Column(Integer, db.ForeignKey('coteries.id'), nullable=False, index=True)
    initiated_by = db.Column(String(200), default='')  # character name
    spend_category = db.Column(String(100), default='')
    trait_name = db.Column(String(100), default='')
    xp_cost_per_member = db.Column(Integer, default=0)
    total_xp_cost = db.Column(Integer, default=0)
    # JSON: {character_name: xp_committed} — tracks who has committed their share
    contributions = db.Column(Text, default='{}')
    # Pending = waiting for member contributions
    # Funded   = all members committed, waiting for staff approval
    # Approved = staff approved, XP deducted from all members
    # Denied   = staff denied
    status = db.Column(String(20), default='Pending', index=True)
    justification = db.Column(Text, default='')
    reviewed_by = db.Column(String(100), default='')
    review_date = db.Column(String(20), default='')
    st_notes = db.Column(Text, default='')
    timestamp = db.Column(String(20), default='')


class DbHuntingSite(db.Model):
    """A NYC hunting location with predator-type DCs, a site bonus, and optional coterie ownership."""
    __tablename__ = 'hunting_sites'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False)
    borough = db.Column(String(100), default='', index=True)
    predator_types = db.Column(Text, default='[]')  # JSON: [{"type": str, "dc": int}]
    bonus = db.Column(Text, default='')
    coterie_id = db.Column(Integer, db.ForeignKey('coteries.id'), nullable=True, index=True)
    active = db.Column(Boolean, default=True, index=True)
    sort_order = db.Column(Integer, default=0)
