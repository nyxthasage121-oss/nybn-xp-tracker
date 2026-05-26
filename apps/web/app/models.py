"""Data classes for NYbN XP Tracker entities."""

from dataclasses import dataclass, field
from .shared_contract import load_json


@dataclass
class Character:
    character_name: str
    player_discord: str = ''
    player_discord_name: str = ''
    clan: str = ''
    age_category: str = ''  # Fledgling, Neonate, Ancilla, Elder, Mortal
    sect: str = ''           # Camarilla, Anarch, Hecata, Autarkis
    active: bool = True
    creation_xp: int = 0
    enemy: str = ''
    date_added: str = ''
    notes: str = ''

    # Computed fields
    earned_xp: int = 0
    approved_spends: int = 0
    available_xp: int = 0
    last_submission: str = ''

    # XP cap (NYbN cap: 350)
    xp_cap_reached: bool = False
    xp_cap_reached_date: str = ''
    retirement_deadline: str = ''
    retired: bool = False
    retired_date: str = ''

    # Ingrained Discipline Flaw
    ingrained_discipline_flaw: bool = False
    ingrained_discipline_name: str = ''
    ingrained_discipline_xp_used: int = 0


@dataclass
class Criteria:
    """A single XP earn criterion. The submission form is built from active criteria."""
    criteria_id: int = 0
    label: str = ''
    description: str = ''
    xp_value: int = 0
    category: str = 'player'   # base / player / staff / helper
    requires_rp_links: bool = True
    requires_text_note: bool = False
    active: bool = True
    sort_order: int = 0


@dataclass
class PlayPeriod:
    period_label: str
    night_number: int = 0
    start_date: str = ''
    end_date: str = ''
    session_number: int = 0
    submissions_open: bool = True
    active: bool = True


@dataclass
class XPClaim:
    """An XP earn submission.

    claimed_criteria is a list of dicts: [{criteria_id, label, xp_value_at_submission}].
    Values are snapshotted at submission time so future criteria edits don't change history.
    """
    row_index: int = 0
    timestamp: str = ''
    character_name: str = ''
    play_period: str = ''

    claimed_criteria: list = field(default_factory=list)
    rp_links: list = field(default_factory=list)
    path: str = 'none'       # none / staff / helper
    helper_note: str = ''

    computed_xp: int = 0
    status: str = 'Pending'  # Pending, Approved, Denied
    approved_xp: int = 0
    reviewed_by: str = ''
    review_date: str = ''
    st_notes: str = ''
    staff_claim_conflict: bool = False


@dataclass
class SpendRequest:
    row_index: int = 0
    timestamp: str = ''
    character_name: str = ''
    spend_category: str = ''
    trait_name: str = ''
    current_dots: int = 0
    new_dots: int = 0
    xp_cost: int = 0
    justification: str = ''
    status: str = 'Pending'
    verified_cost: int = 0
    reviewed_by: str = ''
    review_date: str = ''
    st_notes: str = ''

    # Humanity conditional spend
    is_humanity: bool = False
    humanity_no_frenzy: bool = False
    humanity_no_stains: bool = False
    humanity_humane_act: bool = False

    # Ingrained Discipline Flaw spend
    is_ingrained_discipline: bool = False


@dataclass
class LedgerEntry:
    """A single line in a character's XP ledger — award or spend."""
    row_index: int = 0
    character_name: str = ''
    date: str = ''
    awarded: int = 0
    spent: int = 0
    reason: str = ''
    entered_by: str = ''
    timestamp: str = ''


@dataclass
class AuditEntry:
    timestamp: str = ''
    staff_user: str = ''
    action_type: str = ''
    target_character: str = ''
    details: str = ''


@dataclass
class Coterie:
    coterie_id: int = 0
    name: str = ''
    description: str = ''
    created_at: str = ''
    created_by: str = ''
    active: bool = True
    members: list = field(default_factory=list)   # list of character_name strings


@dataclass
class CoterieSpend:
    coterie_id: int = 0
    coterie_name: str = ''
    initiated_by: str = ''
    spend_category: str = ''
    trait_name: str = ''
    xp_cost_per_member: int = 0
    total_xp_cost: int = 0
    contributions: dict = field(default_factory=dict)  # {character_name: xp_committed}
    status: str = 'Pending'   # Pending / Funded / Approved / Denied
    justification: str = ''
    reviewed_by: str = ''
    review_date: str = ''
    st_notes: str = ''
    timestamp: str = ''


# ── NYbN seed criteria (used to pre-populate the criteria table on first run) ─

NYBN_SEED_CRITERIA = [
    {
        'label': 'Posting',
        'description': 'Posted at least 3 times with at least 4 sentences per post during this night cycle.',
        'xp_value': 3,
        'category': 'base',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': True,
        'sort_order': 1,
    },
    {
        'label': 'Monstrous Action',
        'description': 'Performed a Monstrous Action.',
        'xp_value': 1,
        'category': 'player',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': True,
        'sort_order': 2,
    },
    {
        'label': 'Altruistic Action',
        'description': 'Did something where your character gains no benefit but helps others.',
        'xp_value': 1,
        'category': 'player',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': True,
        'sort_order': 3,
    },
    {
        'label': 'Combat',
        'description': 'At least level 2, damage dealt or taken (Physical and/or Social).',
        'xp_value': 1,
        'category': 'player',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': True,
        'sort_order': 4,
    },
    {
        'label': 'Event',
        'description': 'Being in a scene with an Event or story conclusion.',
        'xp_value': 1,
        'category': 'player',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': True,
        'sort_order': 5,
    },
    {
        'label': 'Writing Prompt',
        'description': 'Completed a Writing Prompt.',
        'xp_value': 1,
        'category': 'player',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': True,
        'sort_order': 6,
    },
    {
        'label': 'Sabbat Character',
        'description': 'Played a Sabbat character (with server threat level 2+).',
        'xp_value': 1,
        'category': 'player',
        'requires_rp_links': True,
        'requires_text_note': False,
        'active': False,   # toggled on via admin panel when needed
        'sort_order': 7,
    },
    {
        'label': 'Staff Activity',
        'description': 'Played an NPC, ran an active storyline, or ran combat with more than three combatants.',
        'xp_value': 1,
        'category': 'staff',
        'requires_rp_links': False,
        'requires_text_note': False,
        'active': True,
        'sort_order': 8,
    },
    {
        'label': 'Helper Activity',
        'description': 'Contributed to 3+ tickets, ran a scene in place of an ST, or played an NPC.',
        'xp_value': 1,
        'category': 'helper',
        'requires_rp_links': False,
        'requires_text_note': True,
        'active': True,
        'sort_order': 9,
    },
]


# ── Constants ─────────────────────────────────────────────────────────────────

CLANS = [
    'Brujah', 'Gangrel', 'Hecata', 'Lasombra', 'Malkavian',
    'Nosferatu', 'Ravnos', 'Salubri', 'Toreador', 'Tremere',
    'Tzimisce', 'Ventrue', 'Banu Haqim', 'The Ministry',
    'Thin-Blood', 'Caitiff',
    'Mortal', 'Ghoul',
]

AGE_CATEGORIES = ['Fledgling', 'Neonate', 'Ancilla', 'Elder', 'Mortal']

SECTS = ['Camarilla', 'Anarch', 'Hecata', 'Autarkis', 'NA']

SPEND_CATEGORIES = load_json('packages/api-contract/spend_categories.json')
