# CLAUDE.md — nybn-xp-tracker

## Project Overview

Monorepo: Flask web app + Discord bot (Node/TypeScript) for managing XP earn submissions,
spend requests, and coterie management for New York by Night (NYbN), a Vampire: The
Masquerade V5 play-by-post server.

Adapted from the MCbN XP Tracker (MIT license). Key NYbN differences from the original:
- XP cap of **350** per character (retirement window: 6 months after cap)
- **5 members** per coterie (same as MCbN; 6+ should split into two allied coteries)
- NYbN XP earn criteria (Posting 3 XP, Monstrous Action, Altruistic Action, Combat, Event, Writing Prompt, Staff Activity, Helper Activity)
- Humanity spend is conditional (4 conditions, player certifies, staff verifies)
- Ingrained Discipline Flaw support (up to 15 XP of extra powers, no sheet slot)
- Timezone: **America/New_York**

```
nybn-xp-tracker/
  apps/
    web/          # Flask app (Python 3.12) — system of record
    bot/          # Discord bot (Node 20 / TypeScript)
  packages/
    api-contract/ # Shared request/response schemas and enums
    rules/        # Shared XP/spend formulas (xp_costs.json)
  infra/          # Deploy scripts
  docs/           # Runbooks and architecture notes
  scripts/        # Local bootstrap and ops scripts
```

## NYbN XP Earn Criteria

Seeded from `apps/web/app/models.py::NYBN_SEED_CRITERIA`. Editable live via the
criteria admin panel — no code changes needed to add/modify/remove criteria.

| Label | XP | Category | Notes |
|---|---|---|---|
| Posting | 3 | base | 3+ posts, 4+ sentences each |
| Monstrous Action | 1 | player | |
| Altruistic Action | 1 | player | |
| Combat | 1 | player | Level 2+, damage dealt or taken |
| Event | 1 | player | Scene with Event or story conclusion |
| Writing Prompt | 1 | player | |
| Sabbat Character | 1 | player | Seeded inactive — toggle on via admin panel |
| Staff Activity | 1 | staff | Mutually exclusive with Helper |
| Helper Activity | 1 | helper | Requires free-text note |

## NYbN XP Spend Costs

Defined in `packages/rules/xp_costs.json`. Cost formula: **new level × multiplier**.

| Trait | Formula |
|---|---|
| Attribute | New level × 5 |
| Skill | New level × 3 |
| New Skill (0→1) | 3 flat |
| Specialty | 3 flat |
| Clan Discipline | New level × 5 |
| Other Discipline | New level × 7 |
| Caitiff Discipline | New level × 6 |
| Ingrained Discipline | Clan discipline cost (max 15 XP total from flaw) |
| Blood Sorcery Ritual | Ritual level × 3 |
| Thin-Blood Alchemy Formula | Formula level × 3 |
| Advantage | 3 per dot |
| Blood Potency | New level × 10 |
| Humanity | New rating × 2 (conditional — 4 conditions required) |

Humanity conditions (player self-certifies, staff verifies):
1. No frenzy in past 2 weeks (IRL)
2. No stains gained in past 2 weeks (mitigated stains don't count)
3. Did something humane OR played path accordingly
4. Can only buy 1 Humanity at a time

## Local Development — Docker (preferred)

```bash
./scripts/bootstrap-local.sh web-only
./scripts/bootstrap-local.sh web+bot
```

Web runs at `http://127.0.0.1:5001`.

## Local Development — Host (alternative)

- Web: `cd apps/web && python -m flask run --port 5001`
- Bot: `cd apps/bot && npm start`

## Environment / Secrets

| App | Local env file | Template |
|-----|---------------|----------|
| web | `apps/web/.env` | `apps/web/.env.example` |
| bot | `apps/bot/.env` | `apps/bot/.env.example` |

- **Never commit `.env` files.**
- Prod DB: Turso (libsql). Local dev: SQLite (auto-created, no config needed).
- Details: `docs/ENV_AND_SECRETS.md`

## Database

- **Production**: Turso — set `DATABASE_URL=libsql+https://...` + `TURSO_AUTH_TOKEN`
- **Local dev**: SQLite — default when `DATABASE_URL` is unset
- Tables created automatically on startup (`db.create_all()`)
- Criteria seeded from `NYBN_SEED_CRITERIA` in models.py on first run if table is empty

## Architecture Principles

- `apps/web` is the authority for validation, approvals, and persistence.
- `apps/bot` calls web API endpoints via service token — never writes to DB directly.
- Shared packages (`packages/`) prevent category/rule drift between web and bot.
- Criteria are database-driven — add/modify/remove via admin panel, no code changes.
- Spend cost calculations live in `packages/rules/xp_costs.json` + `apps/web/app/xp_rules.py`.
- XP cap (350) enforced at claim approval time. Cap reached → retirement window opens (6 months).
- Coterie max members: 6 (enforced in `apps/web/app/db.py::COTERIE_MAX_MEMBERS`).
