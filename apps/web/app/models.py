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
class PlayerProfile:
    """Persistent player data keyed by Discord ID — cubby channel, registration date."""
    discord_id: str
    cubby_channel_id: str = ''
    registered_at: str = ''


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
    period_type: str = 'night'   # night | downtime | timeskip


@dataclass
class ChronicleSettings:
    server_start_date: str = '2023-04-10'
    timeskip_interval_weeks: int = 8
    night_duration_days: int = 14
    downtime_duration_days: int = 2
    has_midnight: bool = True       # Split each night into Dusk→Midnight + Midnight→Sunrise
    xp_frequency: str = 'weekly'   # 'weekly' (split) | 'biweekly' (single window per night)
    notes: str = ''


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
    chasse: int = 0
    lien: int = 0
    portillon: int = 0


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


@dataclass
class CoterieMerit:
    merit_id: int = 0
    coterie_id: int = 0
    character_name: str = ''
    merit_name: str = ''
    dots: int = 1
    merit_type: str = 'purchased'  # purchased / creation / donated
    xp_cost: int = 0
    status: str = 'Pending'        # Pending / Approved / Denied
    justification: str = ''
    reviewed_by: str = ''
    review_date: str = ''
    st_notes: str = ''
    timestamp: str = ''


@dataclass
class CoterieFlaw:
    flaw_id: int = 0
    coterie_id: int = 0
    flaw_name: str = ''
    dots_granted: int = 1
    added_by: str = ''
    added_at: str = ''


@dataclass
class CoterieRequest:
    request_id: int = 0
    name: str = ''
    notes: str = ''
    submitted_by: str = ''
    submitted_by_discord_id: str = ''
    has_enough_members: bool = False
    members_have_met: bool = False
    status: str = 'Pending'   # Pending / Acknowledged / Denied
    st_notes: str = ''
    reviewed_by: str = ''
    review_date: str = ''
    timestamp: str = ''


@dataclass
class HuntingSite:
    site_id: int = 0
    name: str = ''
    borough: str = ''
    predator_types: list = field(default_factory=list)  # [{"type": str, "dc": int}]
    bonus: str = ''
    coterie_id: int | None = None
    coterie_name: str = ''
    active: bool = True
    sort_order: int = 0


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


# ── NYbN seed hunting sites ───────────────────────────────────────────────────

NYBN_SEED_SITES = [
    # ── Manhattan ──────────────────────────────────────────────────────────────
    {'name': 'Inwood Park / Hudson Heights', 'borough': 'Manhattan', 'sort_order': 1,
     'predator_types': [{'type': 'Cleaver', 'dc': 3}, {'type': 'Farmer', 'dc': 3}, {'type': 'Graverobber', 'dc': 2}],
     'bonus': 'Characters gain +1 to Stealth or Survival rolls when acting within forested, stone-lined, or shadowed terrain. Once per story, gain +2 bonus dice on a roll to hide a body, escape pursuit, or perform a ritual/ceremony outdoors.'},
    {'name': 'Harlem', 'borough': 'Manhattan', 'sort_order': 2,
     'predator_types': [{'type': 'Osiris', 'dc': 2}, {'type': 'Sandman', 'dc': 3}, {'type': 'Grim Reaper', 'dc': 3}],
     'bonus': 'Characters gain +1 to Presence or Persuasion rolls when appealing to passion, history, or personal belief. Once per story, if invoking cultural or spiritual meaning in a scene, you may automatically win a tie on a Social test.'},
    {'name': 'Central Park', 'borough': 'Manhattan', 'sort_order': 3,
     'predator_types': [{'type': 'Alley Cat', 'dc': 3}, {'type': 'Pursuer', 'dc': 3}, {'type': 'Farmer', 'dc': 2}],
     'bonus': 'Characters can establish hidden sanctuaries within the park, granting a +1 bonus to rolls made to detect intruders or maintain secrecy.'},
    {'name': 'Times Square / Midtown', 'borough': 'Manhattan', 'sort_order': 4,
     'predator_types': [{'type': 'Roadside Killer', 'dc': 3}, {'type': 'Pursuer', 'dc': 3}, {'type': 'Trapdoor', 'dc': 2}],
     'bonus': 'Characters can blend in with the constant flow of travelers, granting a +1 bonus to rolls made to avoid detection or maintain a low profile.'},
    {'name': 'The Villages', 'borough': 'Manhattan', 'sort_order': 5,
     'predator_types': [{'type': 'Bagger', 'dc': 3}, {'type': 'Siren', 'dc': 2}, {'type': 'Consensualist', 'dc': 3}],
     'bonus': 'Once per story, character may frequent a bar or establishment in the Villages and gain the High-Functioning Addict Merit for the night. Characters with the Addiction Flaw can disregard it while in this location.'},
    {'name': 'Fi-Di (Civic Center)', 'borough': 'Manhattan', 'sort_order': 6,
     'predator_types': [{'type': 'Extortionist', 'dc': 2}, {'type': 'Scene Queen', 'dc': 3}, {'type': 'Montero', 'dc': 3}],
     'bonus': 'Characters exploiting the legal or financial systems of Wall Street gain +1 to Subterfuge or Finance rolls when bribing, navigating bureaucracy, or hiding their trail. Once per night, reroll any failed Social roll involving power dynamics, contracts, or financials.'},
    # ── Brooklyn ───────────────────────────────────────────────────────────────
    {'name': 'Brooklyn Heights', 'borough': 'Brooklyn', 'sort_order': 7,
     'predator_types': [{'type': 'Siren', 'dc': 2}, {'type': 'Scene Queen', 'dc': 3}, {'type': 'Consensualist', 'dc': 3}],
     'bonus': 'Once per night, characters may arrange clandestine meetings or exchanges along the Brooklyn Heights Promenade. Characters receive a +1 bonus to rolls made to conceal such scenes from prying eyes.'},
    {'name': 'Prospect Heights', 'borough': 'Brooklyn', 'sort_order': 8,
     'predator_types': [{'type': 'Sandman', 'dc': 2}, {'type': 'Farmer', 'dc': 3}, {'type': 'Trapdoor', 'dc': 3}],
     'bonus': 'Once per Chronicle, characters may leverage connections in Prospect Heights to gain a temporary Ally whose level equals their Lien Rating for the night. Afterward, the coterie\'s Lien Rating is blanked and recovers at 1-dot per Night.'},
    {'name': 'Coney Island', 'borough': 'Brooklyn', 'sort_order': 9,
     'predator_types': [{'type': 'Alley Cat', 'dc': 2}, {'type': 'Pursuer', 'dc': 3}, {'type': 'Osiris', 'dc': 3}],
     'bonus': 'Characters can reroll one failed Manipulation or Subterfuge roll per session when exploiting the chaotic and festive environment. Once per story, gain temporary 1-dot Haven benefits for a night.'},
    {'name': 'New Lots', 'borough': 'Brooklyn', 'sort_order': 10,
     'predator_types': [{'type': 'Alley Cat', 'dc': 3}, {'type': 'Extortionist', 'dc': 2}, {'type': 'Roadside Killer', 'dc': 3}],
     'bonus': 'Characters gain a +1 bonus to Intimidation or Streetwise rolls when hunting in high-crime or low-surveillance zones. Once per night, characters may reroll a failed Composure or Frenzy check triggered in the area.'},
    {'name': 'Greenwood Cemetery', 'borough': 'Brooklyn', 'sort_order': 11,
     'predator_types': [{'type': 'Graverobber', 'dc': 2}, {'type': 'Cleaver', 'dc': 3}, {'type': 'Montero', 'dc': 3}],
     'bonus': 'Once per Chronicle, characters who spend at least a scene within the cemetery\'s grounds may regain 1 point of Humanity, reflecting the contemplative atmosphere and connection to mortality.'},
    {'name': 'Park Slope', 'borough': 'Brooklyn', 'sort_order': 12,
     'predator_types': [{'type': 'Bagger', 'dc': 2}, {'type': 'Grim Reaper', 'dc': 3}, {'type': 'Cleaver', 'dc': 3}],
     'bonus': 'Characters receive an additional point of Willpower restored during their Daysleep, as this location provides a safe space for rest and recuperation.'},
    # ── Queens ─────────────────────────────────────────────────────────────────
    {'name': 'Long Island City', 'borough': 'Queens', 'sort_order': 13,
     'predator_types': [{'type': 'Scene Queen', 'dc': 3}, {'type': 'Consensualist', 'dc': 3}, {'type': 'Cleaver', 'dc': 3}],
     'bonus': 'Once per story, characters may use the skyline as a backdrop for a social engagement, gaining a +1 bonus to Persuasion rolls when trying to impress or intimidate others through the illusion of wealth or status.'},
    {'name': 'La Guardia Airport', 'borough': 'Queens', 'sort_order': 14,
     'predator_types': [{'type': 'Roadside Killer', 'dc': 2}, {'type': 'Osiris', 'dc': 3}, {'type': 'Montero', 'dc': 3}],
     'bonus': 'Once per Chronicle, characters may feed on international travelers and glean information, gaining a temporary 1-dot Contacts (international). Characters may reroll a single die on a Frenzy check once per story while in La Guardia.'},
    {'name': 'Flushing', 'borough': 'Queens', 'sort_order': 15,
     'predator_types': [{'type': 'Bagger', 'dc': 2}, {'type': 'Farmer', 'dc': 3}, {'type': 'Grim Reaper', 'dc': 3}],
     'bonus': 'Once per story, gain a +1 bonus to Etiquette or Manipulation rolls involving cultural navigation within the Asian community. Characters receive a +1 bonus to Willpower recovery rolls if they spend a scene meditating in the Queens Botanical Gardens.'},
    {'name': 'Middle Village', 'borough': 'Queens', 'sort_order': 16,
     'predator_types': [{'type': 'Graverobber', 'dc': 2}, {'type': 'Sandman', 'dc': 3}, {'type': 'Trapdoor', 'dc': 3}],
     'bonus': 'Characters gain +1 to Occult or Stealth rolls when operating within cemeteries or consecrated grounds. Once per story, after spending 10 minutes in solitude among the graves, a character may ask a yes/no question about a current mystery and receive a cryptic omen (ST discretion).'},
    {'name': 'Jamaica', 'borough': 'Queens', 'sort_order': 17,
     'predator_types': [{'type': 'Alley Cat', 'dc': 3}, {'type': 'Osiris', 'dc': 2}, {'type': 'Pursuer', 'dc': 3}],
     'bonus': 'Characters gain +1 to Persuasion or Insight rolls when appealing to justice, rebellion, or principle. Once per story, you may reroll a failed Social roll if defending a Conviction or inspiring others toward a cause.'},
    {'name': 'Steinway', 'borough': 'Queens', 'sort_order': 18,
     'predator_types': [{'type': 'Extortionist', 'dc': 3}, {'type': 'Scene Queen', 'dc': 2}, {'type': 'Siren', 'dc': 3}],
     'bonus': 'Characters gain +1 to Etiquette or Performance rolls when engaging through shared culture, faith, or artistic representation. Once per story, gain 1 temporary dot of Herd or Allies (lasting 1 night) by invoking community ties.'},
    # ── The Bronx ──────────────────────────────────────────────────────────────
    {'name': 'Pelham Bay', 'borough': 'The Bronx', 'sort_order': 19,
     'predator_types': [{'type': 'Farmer', 'dc': 2}, {'type': 'Pursuer', 'dc': 3}, {'type': 'Osiris', 'dc': 3}],
     'bonus': 'Characters can use the nearby Pelham Bay Park to establish sanctuaries, offering protection from detection. Characters gain a +1 bonus to rolls for remaining unseen or maintaining haven secrecy.'},
    {'name': 'Woodlawn Cemetery', 'borough': 'The Bronx', 'sort_order': 20,
     'predator_types': [{'type': 'Graverobber', 'dc': 2}, {'type': 'Grim Reaper', 'dc': 3}, {'type': 'Cleaver', 'dc': 3}],
     'bonus': 'Characters investigating old graves or tombs may uncover historical secrets. Once per story, roll Investigation or Occult with a +2 bonus to learn something valuable about the dead buried here.'},
    {'name': 'New York Botanical Park (Bronx Park)', 'borough': 'The Bronx', 'sort_order': 21,
     'predator_types': [{'type': 'Farmer', 'dc': 2}, {'type': 'Montero', 'dc': 3}, {'type': 'Trapdoor', 'dc': 3}],
     'bonus': 'Characters gain a +1 bonus to healing rolls or superficial damage recovery if they feed or rest within the Gardens for an entire scene.'},
    {'name': 'Yankee Stadium', 'borough': 'The Bronx', 'sort_order': 22,
     'predator_types': [{'type': 'Extortionist', 'dc': 3}, {'type': 'Siren', 'dc': 3}, {'type': 'Roadside Killer', 'dc': 3}],
     'bonus': 'Characters gain +1 to Strength or Charisma rolls when asserting dominance, organizing groups, or inspiring fear/respect. Once per story, after proving themselves in a physical or social challenge near a sporting event, treat your next roll as if you rolled one additional success.'},
    {'name': 'Fordham University / Belmont', 'borough': 'The Bronx', 'sort_order': 23,
     'predator_types': [{'type': 'Bagger', 'dc': 2}, {'type': 'Scene Queen', 'dc': 3}, {'type': 'Consensualist', 'dc': 3}],
     'bonus': 'Characters who establish contacts within Fordham University may increase their Influence (Academia) by 1 dot temporarily for a single story, representing favors granted by professors or researchers.'},
    {'name': 'Parkside Housing Project', 'borough': 'The Bronx', 'sort_order': 24,
     'predator_types': [{'type': 'Sandman', 'dc': 2}, {'type': 'Alley Cat', 'dc': 3}, {'type': 'Pursuer', 'dc': 3}],
     'bonus': 'The neighborhood\'s rough environment fosters resilience. Characters feeding here gain a +1 bonus to resisting Frenzy checks when in impoverished areas for the rest of the night.'},
    # ── Staten Island ──────────────────────────────────────────────────────────
    {'name': 'Arlington', 'borough': 'Staten Island', 'sort_order': 25,
     'predator_types': [{'type': 'Sandman', 'dc': 2}, {'type': 'Cleaver', 'dc': 3}, {'type': 'Consensualist', 'dc': 3}],
     'bonus': 'Once per Chronicle, a character may gain temporary access to Resources, increasing their rating by 1-dot for a night.'},
    {'name': 'Empire Outlets', 'borough': 'Staten Island', 'sort_order': 26,
     'predator_types': [{'type': 'Scene Queen', 'dc': 2}, {'type': 'Siren', 'dc': 3}, {'type': 'Extortionist', 'dc': 3}],
     'bonus': 'Kindred with the Fame or Influence backgrounds gain a +1 bonus when using these backgrounds at Empire Outlets due to the site\'s association with wealth and status.'},
    {'name': 'University Hospital — North Campus', 'borough': 'Staten Island', 'sort_order': 27,
     'predator_types': [{'type': 'Grim Reaper', 'dc': 3}, {'type': 'Bagger', 'dc': 2}, {'type': 'Osiris', 'dc': 3}],
     'bonus': 'Characters with medical backgrounds (Medicine, Academics) can access state-of-the-art resources. Once per story, use the hospital to reduce Aggravated Damage by 1.'},
    {'name': 'Staten Island Mall', 'borough': 'Staten Island', 'sort_order': 28,
     'predator_types': [{'type': 'Roadside Killer', 'dc': 3}, {'type': 'Trapdoor', 'dc': 2}, {'type': 'Siren', 'dc': 3}],
     'bonus': 'Characters gain +1 to Awareness or Subterfuge rolls while observing or moving through suburban consumer spaces. Once per story, reroll one failed Wits-based roll per night if acting from a position of passive observation.'},
    {'name': "Prince's Bay Lighthouse", 'borough': 'Staten Island', 'sort_order': 29,
     'predator_types': [{'type': 'Pursuer', 'dc': 3}, {'type': 'Alley Cat', 'dc': 3}, {'type': 'Trapdoor', 'dc': 2}],
     'bonus': 'Kindred with occult knowledge may use the lighthouse as a focal point for rituals or to communicate with spirits of those lost at sea. Grants a +1 bonus to Occult-related rolls once per story.'},
    {'name': 'Silver Lake Park', 'borough': 'Staten Island', 'sort_order': 30,
     'predator_types': [{'type': 'Graverobber', 'dc': 3}, {'type': 'Montero', 'dc': 2}, {'type': 'Farmer', 'dc': 3}],
     'bonus': 'Characters with ties to necromancy or death-related disciplines receive a +1 bonus to Oblivion rolls while in the park. The historic immigrant burial grounds have imbued the area with latent supernatural energy.'},
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

SECTS = ['Camarilla', 'Anarch', 'Sabbat', 'Hecata', 'Autarkis', 'NA']

SPEND_CATEGORIES = load_json('packages/api-contract/spend_categories.json')
