# Liandrys2

League of Legends damage calculator: pick champions, levels, items, runes and a combo of actions, and get the exact damage over time as a graph. It is a long-running personal learning project. The goal is to keep learning AND to finish a V1 (see [ROADMAP.md](ROADMAP.md)).

## Working agreements

- **Never commit or push.** The owner commits everything themselves. Make changes in the working tree, then summarize what changed.
- **Explain, don't just do.** This is a learning project: give reasons and trade-offs, especially for design decisions. Ask before changing data formats (models, formula syntax, DB schema).
- **Code style:** everything in English (names, comments, strings). Few comments. Prefer descriptive names and small, compact functions. Comment only the *why* of non-obvious things (e.g. a League mechanic).
- **Be careful with dependency upgrades.** Library updates have broken the project before. Bump versions one at a time, and only with the tests passing.
- `ToDo.md` is the owner's idea collection. Don't restructure it. Planned (open) work lives in `ROADMAP.md`; finished work and decisions with their reasons move to `docs/decisions.md`, so the roadmap stays short.
- **Save context:** one chat per roadmap step. Read files by headings first, then only the needed sections; keep fixture, log and traceback output short.

## Architecture

```
backend/            FastAPI, one codebase, two apps
  src/main.py       user API   :5000  (read-only routers + /simulation)
  src/admin.py      admin API  :5001  (also mounts the `admin` routers under /admin, /enum, /logs)
  src/server/
    database.py     Motor/MongoDB access, one collection per type, all queries
    errors.py       error responses {detail, code, error_id}; tracebacks to alerts.log, failed simulations with their request to simulation.log
    loader/         patchloader.py (orchestration) + <type>_source.py / <type>_builder.py per type + cdragon.py
                    (translator) + champion_patcher.py (diff, validation) + patch_source.py (which patches to load)
    models/         Pydantic v1 models (see below); enums.py is the import-free bottom layer (enums ← models ← simulation ← routes), result.py the response format
    routes/         every module exposes `router` (read) and `admin` (write)
    simulation/     simulation.py (tick queue) + character.py (stats, formulas, applying effects) + pet.py (summoned units)
                    + events.py (queue events) + components.py (QueueComponent, Processed…Properties)
  src/tests/        pytest; static wiki HTML/JSON fixtures in tests/static
  src/conftest.py   shared fixtures
frontend/app/       user UI (Vue 3 + Vite + Tailwind + chart.js) :5173 -> proxies to :5000
frontend/admin/     admin UI (Vue 3 + Vite + Tailwind) :5174 -> proxies to :5001
```

**Data flow:** Riot Data Dragon (lists, base stats, images) + League wiki (scraped details) → loader → MongoDB → the admin editor completes abilities/passives by hand → the user picks a combo → simulation → `effect_list` → chart.

**Patch versioning:** every document carries `patch` (its identity, with the name/id). A new patch copies all documents of the old patch forward; a hotfix overwrites its patch in place (`Patch.build` = CommunityDragon build, `Patch.updated_at` = last hotfix run). Champions are diffed against CommunityDragon (`loader/champion_patcher.py`): `changes` (`list[Change]`, source `data` or `patch_notes`) holds only this patch's changes, and an ability loses `validated` only where the change can break its hand-made rules (table in [docs/decisions.md](docs/decisions.md#automatic-patching)). Summoner spells, items and runes patch the same way (`loader/summonerspell_builder.py`, `loader/item_builder.py`, `loader/rune_builder.py`; one spell, item or rune = one slot, an item's `values` are shared by its active and passives, a rune's are on its passive; stat shards are one document per row with loader-built stats). `validated` means "the manually maintained data is trustworthy for this patch"; `Champion.validated` is computed from its abilities. A patch with `loaded_total_count < total_count` is incomplete, and the next load resumes it. The PBE preview (`Patch.preview`, CDragon's `pbe/` patched forward from live under the coming name, e.g. `16.24.1`) is read-only, skipped by `fetch_patch_latest`, and replaced on each PBE build and on release.

**Models:**
- Every type has `New<Type>` (no id, what the loader writes), `<Type>` (with `_id`) and `Short<Type>` (projection for lists).
- The ability system (`models/rule.py`, see [docs/ability-system.md](docs/ability-system.md)) uses Pydantic 1.10's discriminated unions (`Literal` `type_` + `Field(discriminator="type_")`) and `extra = forbid`. Nested models need no `parse_obj` overrides; the routes take and return the models directly (tests in `tests/test_routes.py`). The hand-entered containers (Ability, Passive, Pet) are `extra = forbid` too, so a typo fails instead of vanishing.
- Champion stats are flat fields (all present), item stats are `dict[Stat, float]` (sparse). This is deliberate.

**Ability system:** abilities, passives and summoner spells hold `rules` (trigger → conditions → actions), `buffs`, `stats`, `inputs` and `stages`; see [docs/ability-system.md](docs/ability-system.md). Values are **formula strings** evaluated in `simulation/formula.py` (`evaluate_formula`, namespace with stats, `target_`/`owner_` prefixes, `stacks_<buff>`, `elapsed_<buff>`, `rank`, `level`, `cooldown`, `cooldown_multiplier`, `elapsed`, scenario inputs, and the loader's named values: `BaseDamage` from the container's `values`, `q.TumbleCDReduction` from another slot at that slot's rank). An ability without `stages` isn't entered yet and raises `NotEnteredError`. Simulation errors are typed (`simulation/exceptions.py`: `ComboError`, `DataError`, `NotEnteredError`, `NotSupportedError`) and `located` adds where they happened.

**Game rules:** [docs/league-mechanics.md](docs/league-mechanics.md) collects the live League mechanics (mitigation order, crit, shields, CC, movement speed, ...) with what the simulation does today. Check it before building simulation logic.

**Simulation:** one tick is 0.033 s like the game server (`TICK_SECONDS`, `TICKRATE` ≈ 30.3). Convert seconds only with `to_ticks` (rounds up to whole ticks and removes float noise). `Simulation.do_combo` walks the actions. `Character.do_action` returns `RuleEvent`s that the simulation queues by tick (delay, travel time); buffs add `BuffTick`/`BuffEnd` events, pets `PetAttackDue`/`PetExpire`. `_process_tick` runs the rules into `QueueComponent`s, and each target `take_effects` (resistances, shields, heals, CC). The simulation owns time; the Character only reacts.

## Commands

```bash
docker compose up                       # full stack (mongo :27017, mongo-express :8081, both APIs, both UIs)
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d   # Raspberry Pi (ARM mongo image)

cd backend && .venv/Scripts/python -m pytest -q        # all tests (Windows venv)
cd backend && .venv/Scripts/python -m pytest -q src/tests/test_simulation.py
```

- Do **not** add an `__init__.py` to `backend/`, or pytest breaks.
- Tests must not touch the real DB. Mock every `db.*` call. Check with an unreachable DB: `MONGODB_HOST=127.0.0.1 MONGODB_PORT=1 MONGODB_USER=x MONGODB_PASSWORD=x pytest`.
- Tests that store images monkeypatch `images.IMAGE_DIR` (see `tests/test_images.py`), or they write into the real `src/images`.
- Debugging in Docker: uncomment the debugpy entrypoint and port in `docker-compose.yml`, then use "Attach to FastAPI (Docker)" in VS Code.
- After renaming tests via script, VS Code's Testing panel needs "Refresh Tests".

## Gotchas

- Everything runs in dev mode with no auth or security on purpose. Credentials come from env vars, set in `docker-compose.yml`.
- Python 3.11 in the container. Pydantic v1 (the v2 migration is planned, but only after everything else is polished).
- `requirements.txt` is a UTF-16 `pip freeze` with unused libs.
