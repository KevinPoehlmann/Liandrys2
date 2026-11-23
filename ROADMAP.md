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
- [x] Commit and push the current state to GitHub

## Phase 1: Simulation correctness ✅

All bugs below were confirmed with probe tests. Each fix gets a regression test.

- [x] Effects after the last action are lost (delayed damage, projectiles, remaining DoT ticks): process the queue until it is empty
- [x] Status effects crash: they are never turned into `ProcessedStatusProperties`
- [x] Stat buffs never apply: `evaluating_stat` is never cleared (e.g. Aatrox AD stays the same with 5 or 10 stacks)
- [x] Damage results vanish from `effect_list` with vamp: `effect_results` is overwritten in the `_process_queue` loop
- [x] Expired shields keep blocking: not reachable, `take_effects` drops expired shields before damage (regression test added)
- [x] Heal results: `max` → `min` (negative overheal)
- [x] Tenacity minimum compares 0.3 to ticks, not seconds
- [x] Found on the way: stat buffs applied to every stat, not only their own `stat`

Quick wins that fit in here:
- [x] `fetch_patch_latest` sorts the patch **string** ("15.9.1" > "15.10.1"); same for `sorted(...)` in the loader
- [x] User UI: changing the patch dropdown doesn't refetch data; the simulation `watch` misses `ability_points`
- [x] Chart: `"Magical"` → `"Magic"` color; the mode toggle (`subtype`/`source`/`total`) has no effect; shields missing in "Tank" (shields now apply per damage component, so damage `value` is health damage)
- [x] Admin UI: `filtered()` uses `this` in `<script setup>` (works in dev, crashes in a production build)

## Phase 2: Ability system (data model)

The core of the project. **Decide first, then build.** Every change here touches model + simulation + editor + tests. The design is in [docs/ability-system.md](docs/ability-system.md).

Decisions:
- [x] **Formula variables:** own namespace with Python-safe names, a generated `target_` set, `by_rank`/`by_level` lookups; `HpScaling` is removed
- [x] **Target per component:** `target` enum (`self | target`, extensible for pets/2v2)
- [x] **Ability vs. passive:** separate containers, shared `Rule = trigger → conditions → actions` and one action vocabulary; named buffs with runtime instances, DoTs are buffs
- [x] **Escape hatch:** `Custom(function, args)` returning normal actions

Building blocks that are missing (each one gets a champion/item from the test group):
- [x] Timed buffs and "next attack" buffs: Sheen/Spellblade, Nasus Q, "+30% AS for 3s"
- [x] `Hit` (on-hit) and `GetHit` (e.g. Thornmail)
- [x] Named stack counters with max, duration and reset: Conqueror, BotRK's Clawing Shadows, Vayne W, Electrocute
- [x] Conditions with an actor (self/target/bearer): executes, "below 30% HP" (range conditions come with distance, Phase 5)
- [x] Recasts (Riven), auto-attack resets (Riven Q, Vayne Q)
- [ ] Cooldown reduction on hit (`ModifyCooldown` is in the model but not built; no test group member needs it, additive)
- [x] ~~Non-linear rank values~~ (`by_rank(...)` lists every rank; the scraper no longer builds effects)
- [x] ~~`extra = "forbid"` on the effect models~~ (the rule models have it; the old effect models are gone)
- [x] Pets (actor ids like `blue.tibbers`, Tibbers)
- [x] Results know their origin: `EffectResult.source` is only an `ActionType` today, so an item/rune proc (Sheen, Kraken, Electrocute) can't be told apart. Add the owning item/rune/buff while the result format is being rebuilt anyway; the post-V1 damage breakdown builds on it

Known gaps found in Phase 1 (fold them into the new design):
- [x] ~~Cast buffs are commented out (`_check_buffs`)~~ (old path removed; stacks come from rules)
- [x] `bonus <stat>` only counts items, not buffs
- [x] ~~A status with `duration` on the EffectComponent~~ (EffectComponent is gone; DoTs are buffs with an interval)

Cleanup once the simulation runs on the new system (not before, the old models still live in these files):
- [x] Delete the old effect models (`effect.py`, `passive_effect.py`, the old `…Properties` and `Condition` in `dataenums.py`; the `Processed…Properties` stay, the new path uses them)
- [ ] Move the simulation runtime types (`QueueComponent`, `ActionEffect`, `AttackspeedStats`) into `simulation/`, and the result types (`EffectResult`, `TickEvent`) into their own model
- [ ] Remove dead code: `ItemStat`, `Mythic`, `Combo`, the unused `MultiValueEnum` import (then `aenum` can leave `requirements.txt`)
- [ ] Rename `dataenums.py` → `enums.py` once it only holds enums and constants. It stays the import-free bottom layer: enums ← models ← simulation ← routes

**Test group:** Veigar, Annie (+Tibbers as a design check), Darius, Vayne, Riven, Vladimir, plus Urgot (W: toggle, attacks made by an ability, on-hit at 50 %), Nidalee (forms, abilities replaced by a buff, rank from R), Sheen, Thornmail, Blade of the Ruined King (replaces Kraken Slayer: current-health on-hit, life steal, melee/ranged), The Collector, Hextech Gunblade (replaces Black Cleaver: item actives, omnivamp), Conqueror, Electrocute (see the design doc for what each covers). One test per combo with the expected damage. Every building block is "done" when its test-group member works.

- [x] Champions: Annie (+Tibbers), Darius, Vayne, Vladimir, Riven, Veigar, Urgot (W)
- [ ] Nidalee: forms (`extra_abilities`, `Buff.replaces`, `ToggleBuff`, `counts_as_cast`, `Buff.range_type`), then Hunted (`ModifyCooldown`, `distance`)
- [x] Items: Sheen, Thornmail, Blade of the Ruined King, The Collector, Hextech Gunblade
- [x] Runes: Conqueror, Electrocute (runes and stat shards in the simulation, adaptive force, cast instances)

## Phase 3: Admin side complete

- [ ] **Data checks on PUT:** run each changed ability once in a mini simulation (dummy target, all ranks), reject with a clear message on error
- [ ] Editor: field for `Champion.adaptive_type`
- [ ] Editor: show save errors (400/422); update `originalChampion` after saving; load `/enum` once and `provide` it
- [ ] PUT without changes should not be an error (today: 400)
- [ ] Migration: `schema_version` per document, an ordered list of migrations, `update_many` instead of one-by-one updates, migrations for all types
- [ ] Log view: probably fixed once the loader is async (Phase 4); also handle the polling race at start

## Phase 4: Loader with little manual work per patch

The loader is parked until it's needed again. Do this before data entry.

- [ ] Scrape each champion's adaptive type (physical/magic) from the wiki into `Champion.adaptive_type`; until then it is entered by hand (fixtures have it)
- [ ] **Automatic stat patching:** re-scrape changed objects, take numbers/stats from the wiki, keep only the manual effects and mark them unvalidated
- [ ] Error handling refactor: dead `urllib` excepts, `_retry` swallowing non-HTTP errors, `gather` without `return_exceptions` (orphaned tasks), blocking `requests.get` inside `async` functions, `image` unbound in `_load_rune`
- [ ] Re-download the 12 zero-byte images
- [ ] CommunityDragon as a data source. Checked for Riven (`raw.communitydragon.org/latest/game/data/characters/<name>/<name>.bin.json`): it has clean numbers per spell (`spellCastTime`/`castFrame` matching the wiki's cast times, cooldowns per rank, missile speeds, `DataValues` like `BaseDamage`/`ADRatio` per rank). `spellTotalTime` looks like a default (1.0 s on many spells), so real animation lengths would need the animation files. Probably more robust than scraping wiki HTML; the wiki's raw templates (`?action=raw`) are the other option.
- [ ] Animation locks after the cast time (e.g. Riven Q uncanceled vs. canceled) from real data instead of assumptions. Then `Lock` can tell an animation from a cast time: item actives can't be used during a cast time, but during a pure animation (wiki)
- [ ] `extra = forbid` for the hand-entered containers (Ability, Passive, Pet) so typos fail; needs a fresh load or an `$unset` of the old `effects` in the DB first

## Phase 5: User side V1

- [ ] Pass runes, summoner spells, item passives/actives and distance from the route into the simulation
- [ ] Crits in the UI: pick crit/no crit per attack below a threshold (e.g. 5 attacks) and show how likely that number of crits is (pseudo-random algorithm, docs/league-mechanics.md); expected value above (`Action.crit` = None)
- [ ] Item groups from `limitations` ("Limited to 1 Spellblade item"): reject two items of one group when picking items
- [ ] Scenario inputs in the UI: stack configuration (placeholder today, e.g. Veigar Q kills) and checkboxes like "wall behind the target" (Vayne E `terrain`)
- [ ] Ability points: lowering the level should drop excess points
- [ ] Ignore outdated simulation responses (race when clicking fast)

## Phase 5½ (optional): AI drafts for data entry

Speeds up Phase 6. Needs the Phase 2 format to be stable and the Phase 3 data checks in place, which catch the AI's mistakes.

- [ ] Decide the route: Claude API from the admin backend (API key, billed per token, a few dollars to tens of dollars for the initial load, cents per patch), or drafting in Claude Code sessions on the Pro subscription (no extra cost, no app integration)
- [ ] The AI writes only the **structure** (trigger, conditions, actions) and references the scraped named values. It never writes numbers itself
- [ ] Output is validated against the rule schema (structured output + `extra = forbid`), then by the Phase 3 dry-run simulation
- [ ] Admin editor: a "Draft with AI" button fills the form; a human reviews, and only a human sets `validated`
- [ ] Per patch, draft only new or structurally changed abilities

## Phase 6: Data entry ⏱️

The clock starts here. Enter champions, items and runes, working from the "only show invalid" list.

---

## After V1: user comfort

Ideas collected for later; mostly frontend.

- Champion selection: class filter with the Data Dragon `tags` (Fighter, Mage, …; not positions, the champion model doesn't store them yet)
- Item shop like in game: tag filters (Data Dragon item `tags`) and a build tree from `from`/`into`
- Damage summary: total physical / magic / true taken, and a breakdown per source
- Item contribution: direct procs via the result's origin (see Phase 2); stat contribution by simulating once without the item (the parts don't add up to the total, stats amplify each other)
- Quick rune pages: first by hand in the admin editor or "recently used" in the browser; later aggregated from the Riot Match-V5 API, which would also give positions for a position filter (needs a production API key, rate limits, a collector job). Riot offers no recommended pages through the API
- Import from a past game: Riot ID → match list → pick a match and a minute → champions, levels, runes, summoner spells, items and ability points of both sides are filled in. Sources: Match-V5 match details (champion, runes, summoners) and timeline (per-minute frames with level; item purchase/sell/undo/destroy and skill level-up events, replayed up to the chosen time). Not in the data: stacks (Veigar Q, Mejai's), so they stay manual. Needs the same production API key as the rune pages, and data for the match's patch (older patches may be missing or unvalidated)
- Build comparison: run the imported state and one or more variants ("Item X instead of Y") side by side in the chart, so you can see which item would have been better at that point
- About page: what the app does, how to use it, how the simulation works and its limits; also the home of the Riot disclaimer
- Feedback / bug report page (once things run roughly): pick champion (or item/rune) + ability, the patch is filled in automatically. Before submitting, show the open reports for that selection with a "same problem" (+1) button, so duplicates become votes instead of new reports. Admin UI gets a list to work through (open / fixed / rejected). Note: this is the first write endpoint on the user API, so it needs spam protection (rate limit, maybe a captcha) and its own collection with insert rights only (fits the separate Mongo users in the backlog)
- Production: disclaimer "not affiliated with Riot Games", register the project in the Riot Developer Portal

## Backlog (after V1 or when needed)

- Pydantic v2, only once everything else is polished
- Security/production: separate Mongo users (`read` for the user backend, `readWrite` for admin), `.env` instead of credentials in compose, no public Mongo/admin ports, production build + nginx, safer `eval`
- Raspberry Pi: deploy without swapping lines (env vars / override file)
- Housekeeping: `requirements.txt` as UTF-8 with direct deps only, Python 3.11 locally too, node 18 → current LTS, unused `axios` in the user app
- Tests: replace hand-made fakes with real models or `Mock` (Pylance warnings)
- `database.py`: wrong logger name, extra `id` field on update, `clear_patch` ignores `patch_left`
- `logger.py`: duplicate formatter, handlers attached twice, `read_text` without encoding
- Routes: duplicate `parse_from_request`, enum endpoints duplicating `/enum`
- Decide: champion stats `int` vs `float` (Pydantic v1 silently truncates floats in `int` fields)
- Manual effect data lives per patch: fixes in older patches don't reach newer ones
- Roles (live patch): top laners reach level 20 (formulas already expect 20 values; the user UI still caps at 18), and each role brings small perks that the request has to ask for
- Mechanics gaps from [docs/league-mechanics.md](docs/league-mechanics.md) (each ⚠ there), build when a test group member or item needs it: resistance reduction with negative resistances, base/bonus resistance split, damage amplification/reduction, bonus crit damage, attack speed cap/floor and `windup_modifier` (check the loader's `/ 100`), attack reset cancelling a windup, ultimate haste and haste cap, heal and shield power, Grievous Wounds, life steal/omnivamp stats, shield types and spell shields, tenacity groups and tenacity from buffs, missing CC types (root, polymorph, charm, flee), multiplicative movement speed bonuses and slow resist, effects before the end of a cast time, channels, pets
- ARAM mode: per-champion modifiers (damage dealt/received, healing, shielding) applied by the simulation; items already have `maps`. Per-map ability values (e.g. Arena Aatrox R) are not planned for V1
