# Liandrys2

League of Legends damage calculator: pick champions, levels, items, runes and a combo of actions, and get the exact damage over time as a graph. It is a long-running personal learning project. The goal is to keep learning AND to finish a V1 (see [ROADMAP.md](ROADMAP.md)).

## Working agreements

- **Never commit or push.** The owner commits everything themselves. Make changes in the working tree, then summarize what changed.
- **Explain, don't just do.** This is a learning project: give reasons and trade-offs, especially for design decisions. Ask before changing data formats (models, formula syntax, DB schema).
- **Code style:** everything in English (names, comments, strings). Few comments. Prefer descriptive names and small, compact functions. Comment only the *why* of non-obvious things (e.g. a League mechanic).
- **Be careful with dependency upgrades.** Library updates have broken the project before. Bump versions one at a time, and only with the tests passing.
- `ToDo.md` is the owner's idea collection. Don't restructure it. Planned work lives in `ROADMAP.md`.

## Architecture

```
backend/            FastAPI, one codebase, two apps
  src/main.py       user API   :5000  (read-only routers + /simulation)
  src/admin.py      admin API  :5001  (also mounts the `admin` routers under /admin, /enum, /logs)
  src/server/
    database.py     Motor/MongoDB access, one collection per type, all queries
    loader/         patchloader2.py (orchestration) + webscraper2.py (wiki scraping) + helper.py
    models/         Pydantic v1 models (see below)
    routes/         every module exposes `router` (read) and `admin` (write)
    simulation/     simulation.py (tick queue) + character.py (stats, formulas, applying effects)
  src/tests/        pytest; static wiki HTML/JSON fixtures in tests/static
  src/conftest.py   shared fixtures
frontend/app/       user UI (Vue 3 + Vite + Tailwind + chart.js) :5173 -> proxies to :5000
frontend/admin/     admin UI (Vue 3 + Vite + Tailwind) :5174 -> proxies to :5001
```

**Data flow:** Riot Data Dragon (lists, base stats, images) + League wiki (scraped details) → loader → MongoDB → the admin editor completes abilities/passives by hand → the user picks a combo → simulation → `effect_list` → chart.

**Patch versioning:** every document carries `patch` + `hotfix`. A new patch copies all documents of the old patch forward. Objects named in the patch notes get `changes` lines and `validated = False`. `validated` means "the manually maintained data is trustworthy for this patch". A patch with `loaded_total_count < total_count` is incomplete, and the next load resumes it.

**Models:**
- Every type has `New<Type>` (no id, what the loader writes), `<Type>` (with `_id`) and `Short<Type>` (projection for lists).
- Polymorphic `props` (EffectComponent, PassiveEffect, BuffAction) are resolved by custom `parse_obj` chains, because Pydantic v1 has no discriminated unions. **Always build models with `.parse_obj(...)`, never `Model(**data)`**, or `props` collapse to the empty base class. For the same reason, admin PUT routes take a raw `Request` + `parse_from_request` and GET routes return `JSONResponse(jsonable_encoder(...))`.
- Champion stats are flat fields (all present), item stats are `dict[Stat, float]` (sparse). This is deliberate.

**Ability system:** an Ability has Effects, and each Effect has EffectComponents (Damage / Heal / Shield / Status, with `props` + `delay`/`duration`/`interval`/`speed`). A Passive has PassiveEffects keyed by `Buff` (Stats, Cast, Hit = on-hit, GetHit = when hit). Values are **formula strings** evaluated with `eval` in `Character._evaluate_formula`. Available variables: stat values, `level`, `rank`, stacks per `ActionType`.

**Simulation:** 30 ticks per second (`TICKRATE`). `Simulation.do_combo` walks the actions. `Character.do_action` produces `EffectComp`s. `_queue_status` schedules them by tick (delay, travel time, DoT ticks). `_process_queue`: the attacker `evaluate`s formulas, the defender `take_effects` (resistances, shields, heals, CC).

## Commands

```bash
docker compose up                       # full stack (mongo :27017, mongo-express :8081, both APIs, both UIs)
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d   # Raspberry Pi (ARM mongo image)

cd backend && .venv/Scripts/python -m pytest -q        # all tests (Windows venv)
cd backend && .venv/Scripts/python -m pytest -q src/tests/test_simulation.py
```

- Do **not** add an `__init__.py` to `backend/`, or pytest breaks.
- Tests must not touch the real DB. Mock every `db.*` call. Check with an unreachable DB: `MONGODB_HOST=127.0.0.1 MONGODB_PORT=1 MONGODB_USER=x MONGODB_PASSWORD=x pytest`.
- `PATHS`/`URLS` in patchloader2 are read at import time, so mocking `info_loader` in a test has no effect. Mock file writes (`Path.write_bytes`) instead, or tests write into the real `src/images`.
- Debugging in Docker: uncomment the debugpy entrypoint and port in `docker-compose.yml`, then use "Attach to FastAPI (Docker)" in VS Code.
- After renaming tests via script, VS Code's Testing panel needs "Refresh Tests".

## Gotchas

- Everything runs in dev mode with no auth or security on purpose. Credentials come from env vars, set in `docker-compose.yml`.
- Python 3.11 in the container. Pydantic v1 (the v2 migration is planned, but only after everything else is polished).
- `requirements.txt` is a UTF-16 `pip freeze` with unused libs.
