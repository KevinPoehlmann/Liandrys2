# Roadmap to V1

`ToDo.md` stays the idea collection. This file is the plan: what V1 means, and the order to get there.

## What V1 means

- **User side:** nearly all champions, items, runes and summoner spells work. Real oddballs (e.g. Aphelios) may be missing. Click a combo together and see the damage in the graph.
- **Admin side: complete.** Every ability/passive, except the weirdest, can be clicked together in the editor. Migration is complete.
- **Data checks:** every manual change sent to the server is checked automatically, so no ability gets entered that the simulation can't run.

**The constraint that sets the order:** Riot patches every 2 weeks. Once real data entry starts, `changes` pile up whenever work pauses. So data entry comes **last**. Everything that changes the data format or the amount of manual work per patch has to be done first.

---

## Phase 0: Safety net ✅

- [x] All tests green again (234), and no test touches the real DB
- [x] Bugs found on the way: hotfix year came from `datetime.now()`, the suffix regex broke "August", broken images (write before download), `abort_event`, patch `timestamp`
- [ ] Commit and push the current state to GitHub

## Phase 1: Simulation correctness

All bugs below were confirmed with probe tests. Each fix gets a regression test.

- [ ] Effects after the last action are lost (delayed damage, projectiles, remaining DoT ticks): process the queue until it is empty
- [ ] Status effects crash: they are never turned into `ProcessedStatusProperties`
- [ ] Stat buffs never apply: `evaluating_stat` is never cleared (e.g. Aatrox AD stays the same with 5 or 10 stacks)
- [ ] Damage results vanish from `effect_list` with vamp: `effect_results` is overwritten in the `_process_queue` loop
- [ ] Expired shields keep blocking: `_use_shields` ignores expiry
- [ ] Heal results: `max` → `min` (negative overheal)
- [ ] Tenacity minimum compares 0.3 to ticks, not seconds

Quick wins that fit in here:
- [ ] `fetch_patch_latest` sorts the patch **string** ("15.9.1" > "15.10.1"); same for `sorted(...)` in the loader
- [ ] User UI: changing the patch dropdown doesn't refetch data; the simulation `watch` misses `ability_points`
- [ ] Chart: `"Magical"` → `"Magic"` color; the mode toggle (`subtype`/`source`/`total`) has no effect; shields missing in "Tank"
- [ ] Admin UI: `filtered()` uses `this` in `<script setup>` (works in dev, crashes in a production build)

## Phase 2: Ability system (data model)

The core of the project. **Decide first, then build.** Every change here touches model + simulation + editor + tests.

Decisions to make:
- [ ] **Formula variables:** names with spaces (`bonus ad`, `target's armor`) are SyntaxErrors in `eval`. Choose Python-safe names (`bonus_ad`, `target_armor`) and adjust what the scraper writes
- [ ] **Target per component:** today every component hits `action.target`, so self-heals and shields land on the enemy. Add `target: self | target`
- [ ] **Ability vs. passive:** keep them separate, or use one shared shape `trigger → conditions → actions`, with cost/cooldown kept on the ability?
- [ ] **Escape hatch** for truly weird mechanics: a named Python function per special case instead of growing the generic system forever

Building blocks that are missing (each one gets a champion/item from the test group):
- [ ] Timed buffs and "next attack" buffs: Sheen/Spellblade, Nasus Q, "+30% AS for 3s"
- [ ] `Hit` (on-hit) and `GetHit` (e.g. Thornmail)
- [ ] Named stack counters with max, duration and reset: Conqueror, Kraken
- [ ] Conditions with an actor (self/target): executes, "below 30% HP"; use `ConditionType.RANGE`
- [ ] Recasts, auto-attack resets, cooldown reduction on hit
- [ ] Non-linear rank values: `parse_formula_from_list` assumes linear steps (needs a lookup like `[40, 65, 90][rank - 1]`)
- [ ] `extra = "forbid"` on the effect models, so typos in field names fail instead of being silently dropped
- [ ] Later: pets (needs an actor concept beyond `blue`/`red`)

**Test group:** pick 5–6 champions with very different mechanics, plus a few items and runes. One test per combo with the expected damage. Every building block is "done" when its test-group member works.

## Phase 3: Admin side complete

- [ ] **Data checks on PUT:** run each changed ability once in a mini simulation (dummy target, all ranks), reject with a clear message on error
- [ ] Editor: show save errors (400/422); update `originalChampion` after saving; load `/enum` once and `provide` it
- [ ] PUT without changes should not be an error (today: 400)
- [ ] Migration: `schema_version` per document, an ordered list of migrations, `update_many` instead of one-by-one updates, migrations for all types
- [ ] Log view: probably fixed once the loader is async (Phase 4); also handle the polling race at start

## Phase 4: Loader with little manual work per patch

The loader is parked until it's needed again. Do this before data entry.

- [ ] **Automatic stat patching:** re-scrape changed objects, take numbers/stats from the wiki, keep only the manual effects and mark them unvalidated
- [ ] Error handling refactor: dead `urllib` excepts, `_retry` swallowing non-HTTP errors, `gather` without `return_exceptions` (orphaned tasks), blocking `requests.get` inside `async` functions, `image` unbound in `_load_rune`
- [ ] Re-download the 12 zero-byte images
- [ ] Check: can CommunityDragon provide ability numbers/formulas automatically? (unverified idea)

## Phase 5: User side V1

- [ ] Pass runes, summoner spells, item passives/actives and distance from the route into the simulation
- [ ] Stack configuration (placeholder in the UI)
- [ ] Ability points: lowering the level should drop excess points
- [ ] Ignore outdated simulation responses (race when clicking fast)

## Phase 6: Data entry ⏱️

The clock starts here. Enter champions, items and runes, working from the "only show invalid" list.

---

## Backlog (after V1 or when needed)

- Pydantic v2 (removes the `parse_obj` chains and the Request/JSONResponse workarounds), only once everything else is polished
- Security/production: separate Mongo users (`read` for the user backend, `readWrite` for admin), `.env` instead of credentials in compose, no public Mongo/admin ports, production build + nginx, safer `eval`
- Raspberry Pi: deploy without swapping lines (env vars / override file)
- Housekeeping: `requirements.txt` as UTF-8 with direct deps only, Python 3.11 locally too, node 18 → current LTS, unused `axios` in the user app
- Tests: replace hand-made fakes with real models or `Mock` (Pylance warnings)
- `database.py`: wrong logger name, extra `id` field on update, `clear_patch` ignores `patch_left`
- `logger.py`: duplicate formatter, handlers attached twice, `read_text` without encoding
- Routes: duplicate `parse_from_request`, enum endpoints duplicating `/enum`
- Decide: champion stats `int` vs `float` (Pydantic v1 silently truncates floats in `int` fields)
- Manual effect data lives per patch: fixes in older patches don't reach newer ones
