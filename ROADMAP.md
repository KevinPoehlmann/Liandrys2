# Roadmap to V1

`ToDo.md` stays the idea collection. This file is the plan: what V1 means, and the order to get there.

## What V1 means

- **User side:** nearly all champions, items, runes and summoner spells work. Real oddballs (e.g. Aphelios) may be missing. Click a combo together and see the damage in the graph.
- **Admin side: complete.** Every ability/passive, except the weirdest, can be clicked together in the editor. Migration is complete.
- **Data checks:** every manual change sent to the server is checked automatically, so no ability gets entered that the simulation can't run.

**The constraint that sets the order:** Riot patches every 2 weeks. Once real data entry starts, `changes` pile up whenever work pauses. So data entry comes **last**. Everything that changes the data format or the amount of manual work per patch has to be done first.

---

## Phase 0: Safety net ✅

Done, see [docs/decisions.md](docs/decisions.md#phase-0-safety-net).

## Phase 1: Simulation correctness ✅

Done, see [docs/decisions.md](docs/decisions.md#phase-1-simulation-correctness).

## Phase 2: Ability system (data model) ✅

Done, see [docs/decisions.md](docs/decisions.md#phase-2-ability-system-data-model). Design in [docs/ability-system.md](docs/ability-system.md).

## Phase 3: Loader with little manual work per patch

The loader only collects data (numbers, named values, texts, cast times) and builds no structure. Decisions, sources, the validation table for automatic patching and what is built: [docs/decisions.md](docs/decisions.md#phase-3-loader-with-little-manual-work-per-patch). Build order: (1) champions first load ✅, (2) champions patching (in progress), (3) summoner spells, (4) items incl. actives, (5) runes.

**Next (champions patching):**
- [ ] **Patch notes through the wiki API** instead of the HTML scraper. Decided: wikitext only, no HTML fallback (one parser; the HTML markup just changed under us). The page is structured: `;{{ci|Darius}}` = champion, `* {{ai|Decimate|Darius}}` = ability, `** …` = line, `* Stats` = champion level. Templates become readable text (`{{ap|9 to 4}}` ⇒ "9 to 4"; the per-rank values are only computed by the template, and our numbers come from CDragon anyway). Hotfix sections too (`=== October 22nd Hotfix ===`). The HTML fix in `webscraper2` is a stopgap until then
- [ ] **Name dictionary** wiki ⇔ Data Dragon for all four types, used when fetching and when matching patch notes. Champions: match by name, then by Data Dragon id (`{{ci|Nunu}}` is the id of "Nunu & Willump"). Merge the existing `itemWikiNames`/`runeWikiNames` from `info.json`
- [ ] **Translator: `AbilityResourceByCoefficientCalculationPart`** (decided over a diff workaround). Ryze W's `WDamageCalc = BaseDamage + 0.6 × AP + 0.03 × bonus mana` is untranslated today, so the 26.21 change 0.6 ⇒ 0.7 is invisible to the diff (it compares only the structure of untranslated calculations). Translated, it becomes a named value and the normal path applies. Check which other unknown part types the 16.21 data has (`unsupported` over all champions)
- [ ] Hotfixes (decided: overwrite the patch, see decisions). Open: does `hotfix` stay part of a document's identity or become "last updated"

**Open from the 16.20 → 16.21 run** (throwaway DB `liandrys-patchtest`, port 27018, kept for further runs and Phase 4):
- [ ] An extra ability whose numbers live in another slot's values (Nidalee's Pounce uses R's `PounceDamage`) is unvalidated as "patch notes only" although the data line exists on R
- [ ] Ammo abilities: `mAmmoRechargeTime` (52 spells, Zyra W) is not read
- [ ] Fiddlesticks' missile speed is 0 (wiki 1750; attack spell `FiddleSticksBasicAttack`, probably case)
- [ ] Karthus has his cast offset only in `critAttacks` (wiki 0.04375); the basic attack's default 0 is used, the cross-check warns
- [ ] Varus Q `TotalDamageMax` refers to a hashed name (`{b3ef3984}`)
- [ ] Vayne's attack speed ratio is 0.67 in CDragon, the wiki has 0.658 (her base attack speed). Check in the practice tool
- [ ] Levels 19/20 (practice tool): interpolations continue past 18 by default (`mScalePastDefaultMaxLevel` only appears as `false`; the wiki agrees for Darius' bleed). Breakpoint formulas continue too, unconfirmed: Tibbers' HP (fixture 4000 at 19/20, translator 4350/4700), Annie E's movement speed (fixture stops at 18, CDragon continues)
- [ ] Refresh the fixture `values` from the loader (current patch) and update the expectations, each checked against the wiki. Known changes: Annie Q (80–240 ⇒ 80–260) and W (70–250 ⇒ 70–230), Vayne W (6–10 % / 50–110 ⇒ 4–10 % / 40–100), Urgot R cooldown (120/90/60 ⇒ 100/85/70), Annie E cooldown (check `Cooldown.values`)

**Later in this phase:**
- [ ] Named values per ability with stable names (`BaseDamage`, `ADRatio`, …) for the other three types; the rule editor (Phase 4) offers them for selection
- [ ] Description texts for the other three types (champions: CDragon tooltip + wiki templates, see decisions)
- [ ] Images: stage images (Sion W recast), items, runes and summoner spells with their types
- [ ] Error handling refactor: dead `urllib` excepts, `_retry` swallowing non-HTTP errors, `gather` without `return_exceptions` (orphaned tasks), blocking `requests.get` inside `async` functions, `image` unbound in `_load_rune`
- [ ] The patchloader tests write into the real `src/logs` (e.g. `liandrys_all.log`); mock the loggers like `tests/test_errors.py` does
- [ ] Re-download the 12 zero-byte images
- [ ] Left from Phase 2 for the scraper rework, because only the scraper uses them: the pseudo stats in `Stat` (`target's armor`, `units`, `Charge`, …), `DamageType` `Default`/`Non-Damaging`/`See Notes`/`Spell damage`, the `ERROR` members and the `from_str` alias maps
- [ ] PBE preview (V1, after the base loader): CDragon mirrors the PBE (`pbe/`, e.g. 16.24 while 26.23 is live) in the same format, about two weeks ahead. Load it as a provisional next patch, clearly marked, replaced on release. PBE values still change, and some never ship
- [ ] Dash and leap travel times (Nidalee's Pounce lands at the cast today), e.g. from CommunityDragon's spell data or other sources
- [ ] Animation locks after the cast time (e.g. Riven Q uncanceled vs. canceled) from real data instead of assumptions. Then `Lock` can tell an animation from a cast time (item actives can't be used during a cast time, but during a pure animation). Why CDragon doesn't help yet: see decisions, "Cast times and animations"
- [ ] Fresh load into the new format
- [ ] `extra = forbid` for the hand-entered containers (Ability, Passive, Pet) so typos fail; needs a fresh load or an `$unset` of the old `effects` in the DB first


## Phase 4: Admin side complete

- [ ] **Rule editor** for the new format: rules (trigger, conditions, actions), buffs, stats, inputs, stages, pets, `Custom`. Values reference the named values from the loader. The current editor still has only the old effect components
- [ ] **Data checks on PUT:** run each changed ability once in a mini simulation (dummy target, all ranks), reject with a clear message on error
- [ ] Editor: field for `Champion.adaptive_type` (only if the loader can't scrape it)
- [ ] Editor: show save errors (400/422); update `originalChampion` after saving; load `/enum` once and `provide` it
- [ ] PUT without changes should not be an error (today: 400)
- [ ] Pet stats from CDragon: pets are characters of their own (`annietibbers`) with a `CharacterRecord`, so `champion_stats` almost fits (windup, range, movement speed). Their real health comes from the summoning ability's calculation (`TibbersTotalHP`), the record's 850 + 150 per level look like placeholders. Tibbers' base attack speed 1.736 is the top of the enrage table (decays through `TibbersAttackSpeedDecay`?)
- [ ] Pet snapshots: Tibbers keeps Annie's AP from the moment he spawns, but today every pet formula reads the owner's current stats. The pet instance should hold its owner-dependent values, evaluated once at the summon; the pet definition says which ones snapshot (other pets may scale live)
- [ ] **Validating across patches** (`changes` only holds the changes of its own patch, see Phase 3):
  - Editing an ability whose previous patch is unvalidated shows a warning (not a block) with the `changes` of every patch since the last validated version, so they can be built in one go. A patch can be skipped (e.g. Riot reverts a change one patch later)
  - No warning for abilities that were never validated: they are entered from the current data
  - Validating copies the hand-made part (rules, buffs, stages, …) forward into every later patch that is still unvalidated; `values` stay per patch. A later patch that was already edited by hand is not overwritten silently (hint, you decide). The later patches stay unvalidated, they have their own `changes`
  - Idea: also copy backward into older patches as long as the ability had no `changes` in between (first entry in 26.30 also fills 26.29, … until the patch after which a change appears)
- [ ] Migration (needed from the fresh load on): `schema_version` per document, an ordered list of migrations, `update_many` instead of one-by-one updates, migrations for all types
- [ ] Log view: probably fixed once the loader is async (Phase 3); also handle the polling race at start

AI drafts as a pilot, in Claude Code sessions on the Pro subscription (no API key, no app integration yet; the rule editor stays for review and for the cases the AI gets wrong):
- [ ] Workflow: Claude Code reads the raw data, writes the rules and sends them through the admin PUT, so the data checks apply like for manual entry
- [ ] The AI writes only the **structure** (trigger, conditions, actions) and references the scraped named values. It never writes numbers itself
- [ ] Output is validated by the PUT: the rule models (`extra = forbid`), then the dry-run simulation of the data checks
- [ ] A human reviews in the editor, and only a human sets `validated`
- [ ] Pilot: draft a handful of champions, items, runes and summoner spells, so Phase 5 has finished objects to test the frontend with

## Phase 5: User side V1

- [ ] Pass runes, summoner spells, item passives/actives and distance from the route into the simulation
- [ ] Crits in the UI: pick crit/no crit per attack below a threshold (e.g. 5 attacks) and show how likely that number of crits is (pseudo-random algorithm, docs/league-mechanics.md); expected value above (`Action.crit` = None)
- [ ] Item groups from `limitations` ("Limited to 1 Spellblade item"): reject two items of one group when picking items
- [ ] Scenario inputs in the UI: stack configuration (placeholder today, e.g. Veigar Q kills) and checkboxes like "wall behind the target" (Vayne E `terrain`)
- [ ] Ability points: lowering the level should drop excess points
- [ ] Ignore outdated simulation responses (race when clicking fast)
- [ ] Error display: show what doesn't work instead of a blank page. A `getJson(url, what)` wrapper in `utils/fetch.ts` for every fetch (today `onMounted`/`loadPatchData` check neither `res.ok` nor errors), an error bar naming the function ("could not load items for patch 25.1", error id), reactions per `code` (e.g. "Veigar Q isn't entered yet"), and `app.config.errorHandler` as the last net for render errors
- [ ] Decide how much of an error the user sees per `code`. Today `detail` carries the full message, internals included (fine in dev mode)
- [ ] Look over the simulation with the UI in hand. Open question: one timeline for both champions (today: the next action waits for the previous cast, so Red can't act during Blue's cast) or one per champion (defender actions like shields or Zhonya at the same time). Decides the `Action` format and whether the combo UI has one lane or two; `windup_cancel` resetting `self.tick` is already a workaround for per-champion timing

## Phase 6: AI drafts, improved and scaled

Builds on the Phase 4 pilot with what Phase 5 taught. Speeds up Phase 7.

- [ ] Fold the format changes from Phase 5 into the prompt and schema
- [ ] Measure accuracy: draft the hand-checked set (test group + pilot) again and compare with the stored rules
- [ ] Claude API from the admin backend (API key, billed per token: a few dollars to tens of dollars for the initial load, cents per patch)
- [ ] Admin editor: a "Draft with AI" button fills the form
- [ ] Draft in bulk for everything that is still missing; a human reviews, and only a human sets `validated`
- [ ] Per patch, draft only new or structurally changed abilities automatically (which ones changed is detected by the loader, Phase 3)

## Phase 7: Data entry ⏱️

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
- Tooltips: hovering an ability, item, rune or summoner spell shows its description and values (from the raw data, see Phase 3). Riot's tooltip placeholders are our named values, so they can be filled with the current rank and stats ("220 magic damage" at 100 AP); a few (`@f1@`) are computed by the game at runtime and stay unknown
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
- ~~Manual effect data lives per patch: fixes in older patches don't reach newer ones~~ (Phase 4: validating copies forward)
- Roles (live patch): top laners reach level 20 (formulas already expect 20 values; the user UI still caps at 18), and each role brings small perks that the request has to ask for
- Mechanics gaps from [docs/league-mechanics.md](docs/league-mechanics.md) (each ⚠ there), build when a test group member or item needs it: resistance reduction with negative resistances, base/bonus resistance split, damage amplification/reduction, bonus crit damage, attack speed cap/floor, attack reset cancelling a windup, ultimate haste and haste cap, heal and shield power, Grievous Wounds, life steal/omnivamp stats, shield types and spell shields, tenacity groups and tenacity from buffs, missing CC types (root, polymorph, charm, flee), multiplicative movement speed bonuses and slow resist, effects before the end of a cast time, channels, pets
- ARAM mode: per-champion modifiers (damage dealt/received, healing, shielding) applied by the simulation; items already have `maps`. Per-map ability values (e.g. Arena Aatrox R) are not planned for V1
