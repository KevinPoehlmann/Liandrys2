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
- [x] ~~Cooldown reduction on hit~~ (`ModifyCooldown` is built with Nidalee; on-hit reductions use it in a rule)
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
- [x] Move the simulation runtime types into `simulation/` (`QueueComponent` and the `Processed…Properties` → `components.py`, `ActionEffect` → `events.py`), the result types (`EffectResult`, `TickEvent`, `Origin`) into `models/result.py`, and `AttackspeedStats` into `webscraper2.py` (`AbilityStat` was unused and is gone)
- [x] Remove dead code: `ItemStat`, `Mythic` (test_patchloader2 only has an item named "Mythic Cleaver"), `Combo`, `MultiValueEnum` and `aenum` in `requirements.txt`; `re`/`ClassVar` stay (`Actor`), `StatMode.PERCENT` stays (Rabadon, see the design doc)
- [x] Rename `dataenums.py` → `enums.py` (no clash with the stdlib `enum`; `routes/enums.py` is the enum route, a different package). It stays the import-free bottom layer: enums ← models ← simulation ← routes
- Left for the scraper rework (Phase 3), because only the scraper uses them: the pseudo stats in `Stat` (`target's armor`, `units`, `Charge`, …), `DamageType` `Default`/`Non-Damaging`/`See Notes`/`Spell damage`, the `ERROR` members and the `from_str` alias maps

**Test group:** Veigar, Annie (+Tibbers as a design check), Darius, Vayne, Riven, Vladimir, plus Urgot (W: toggle, attacks made by an ability, on-hit at 50 %), Nidalee (forms, abilities replaced by a buff, rank from R), Sheen, Thornmail, Blade of the Ruined King (replaces Kraken Slayer: current-health on-hit, life steal, melee/ranged), The Collector, Hextech Gunblade (replaces Black Cleaver: item actives, omnivamp), Conqueror, Electrocute (see the design doc for what each covers). One test per combo with the expected damage. Every building block is "done" when its test-group member works.

- [x] Champions: Annie (+Tibbers), Darius, Vayne, Vladimir, Riven, Veigar, Urgot (W)
- [x] Nidalee forms (`extra_abilities`, `Buff.replaces`, `ToggleBuff`, `counts_as_cast`, `Buff.range_type`)
- [x] Nidalee Hunt (`ModifyCooldown`, `distance`)
- [x] Items: Sheen, Thornmail, Blade of the Ruined King, The Collector, Hextech Gunblade
- [x] Runes: Conqueror, Electrocute (runes and stat shards in the simulation, adaptive force, cast instances)

Error handling (the base for the Phase 4 data checks and the Phase 5 error display):
- [x] Rules that trigger each other without a delay never leave their tick (the request hangs): stop after `MAX_RULE_EVENTS_PER_TICK` with the rules involved
- [x] Errors in queued effects (projectiles, DoT ticks, rules after the last action) name the tick and the rule's origin (`phase="effect"`) instead of the action running at that moment, or a 500
- [x] Exception types with context: champion, container, stage and rule number, formula ("Veigar ability 'Q', stage 1, rule 1: Unknown variable in formula …"). Typed errors (`ComboError`, `DataError`, `NotEnteredError`, `NotSupportedError`) set the response `code`; unknown buff and pet names are a `DataError` instead of a bare `KeyError`
- [x] Backend safety net: error responses are `{detail, code, error_id}` (`code`: `invalid_combo | invalid_data | not_entered | not_supported | internal`). Unexpected errors in any route log their traceback with the id to `alerts.log`; failed simulations log the whole request to `simulation.log`, so they can be replayed as a test

## Phase 3: Loader with little manual work per patch

Comes before the admin phase: the loader decides which named values exist per ability (the editor offers them for selection), and a fresh load into the new format is cheaper than migrating the old documents, which hold no valuable manual data yet.

The loader only collects data (numbers, named values, texts, cast times) and builds no structure. Structure comes from manual entry (Phase 4) or AI drafts (pilot in Phase 4, scaled in Phase 6).

- [x] **Decided: raw data is stored.** The whole CDragon file per object and patch goes into its own collection, separate from the finished objects and never read by the user API (measured for Veigar: 133 KB with tooltips and wiki templates, so ≈ 23 MB per patch for champions). It is the lookup for manual entry and the source when later features need more fields (dash times, animations), without reloading old patches. Not relying on CDragon keeping old folders forever
- [x] **Decide:** the loader stores everything it scrapes in its own raw models, so nothing gets lost. The finished objects (`Champion`, `Ability`, …) are built from the raw data and keep only what the simulation needs. Open: are the numbers copied into the finished objects (a build step reruns every patch) or referenced by name and resolved at simulation time? Either way the hand-made structure must survive a new patch
  - **Decided: reference by name.** Each document has a loader-owned `values` field (`BaseDamage = [80, 120, …]`, overwritten every patch) next to the hand-made rules, which use the name (`BaseDamage + APRatio * ap`) and are never touched by a patch. The simulation resolves the name by rank like `by_rank(...)`. No build step, and "manual effect data lives per patch" (backlog) shrinks because the structure changes less often. Risk: Riot renames a value; the loader sees that a name used by a rule is gone and marks the ability unvalidated
  - **Formula syntax:** rules use Riot's names as they are (no own names, they are the link between patches). A bare name is the rule's own ability; other abilities with a prefix (`q.TumbleCDReduction`). No `by_rank`/`by_level` in hand-written formulas: a `DataValues` name resolves by rank (all lists have 7 entries = rank 0–6; constants are equal everywhere), and level scaling only appears in `mSpellCalculations`, which the loader translates into our syntax once (Darius: `BleedDamagePerStack = "by_level(13, …, 30) + 0.3 * bonus_ad"`). Calculations are named values too, so a rule is often just `amount: "TotalDamage"`; a formula in `amount` is still allowed where Riot's tooltip calculation doesn't cover the mechanic (Veigar R's missing-HP scaling). The translator knows the ~11 part types and reports unknown ones instead of guessing. A patch that changes a calculation's structure (not just numbers) is taken over but marks the ability unvalidated
  - ✅ **Renamed `scaling` → `amount`** in `Damage`, `Attack`, `Heal`, `Shield` and `PetAttack` (same name as `ModifyCooldown`/`PayCost`). The old admin editor components still say `scaling`; they are replaced by the Phase 4 rule editor
  - **Everything the loader delivers goes into `values`; every formula field is hand-owned**, also `cost` and `cooldown`. The loader adds the spell fields under Riot's field names (`cooldownTime`, `mana`; they can't clash with the mostly capitalized `DataValues`, Gunblade has its own `Cooldown`), and `cooldown`/`cost` default to those names. A formula like Veigar W's (`cooldownTime` is 0 there, the script uses `BaseCooldown`) survives every patch
  - Not now: a hand-owned `formulas` field for own named formulas (separate from the loader's `values`, which every patch overwrites). Purely additive, can come later if `amount` formulas get messy
  - To clarify when building the patch flow: does CDragon show mechanic changes? Likely signals: value names added/removed, changed `mSpellCalculations`, changed tooltip text. Behavior that lives only in game scripts is not exported, so the wiki patch notes probably stay a second net (objects named there get flagged)
- [ ] Named values per ability with stable names (`BaseDamage`, `ADRatio`, …), so rules can reference them. The rule editor (Phase 4) offers them for selection, and AI drafts (Phase 4/6) depend on them
- [ ] Store each ability's description text (tooltip / wiki text): shown in the editor for manual entry, and the input for AI drafts (Phase 4/6)
  - **Decided:** the CDragon tooltip (`lol.stringtable.json`, e.g. `spell_veigarbalefulstrike_tooltip`) is loader-owned and required; a changed tooltip is a validation signal. Its placeholders are our names (`@TotalDamage@`), Riot's cross-references match our prefix idea (`@Spell.VeigarPassive:dQKillStacks@`)
  - The wiki text with its notes is required for the first load: what the game logic decides (spell shield interaction, which abilities can be cast during others like Riven E → R, on-hit, can't crit) is not in CDragon. Stored as text, not parsed into fields. On patches, the full text is refetched when the wiki page has a newer revision (wiki API revision id), so a late wiki edit is picked up on a later run; patch note lines stay in `changes`. A missing or outdated wiki text blocks nothing
  - CDragon's hints (tooltip tags like `<magicDamage>`, spell tags like `Trait_AttackReset`/`Trait_Shield`, flags like `mCantCancelWhileWindingUp`) are shown in the editor as suggestions. Crit hints: Vayne Q has an explicit `CanBonusDamageCrit = 0`; Darius W's `ADRatio` is the whole attack (1.4–1.6 × AD) while Vayne Q's `TotalADRatio` is only the bonus, which may tell whether the bonus can crit (check against the wiki)

- [ ] Read each champion's adaptive type (physical/magic) into `Champion.adaptive_type` from `Module:ChampionData/data` (`adaptivetype`); until then it is entered by hand (fixtures have it)
- [ ] **Automatic patching:** load the new CDragon data, overwrite `values`, copy the hand-made part forward unchanged, and decide per ability whether it stays validated:

  | Change | Result |
  |---|---|
  | Only numbers | stays validated |
  | Structure of a calculation that a rule uses by name, fully understood by the translator | stays validated (the rule follows automatically) |
  | Structure of a calculation that no rule uses by name while rules use its values (the rule rebuilt it by hand), or a part the translator doesn't know | unvalidated |
  | A name a rule uses is gone | unvalidated |
  | A new name appeared | unvalidated (probably a new mechanic) |
  | Tooltip text changed, numbers equal | unvalidated |
  | Named in the wiki patch notes, but nothing changed in CDragon | unvalidated, marked "patch notes only" (mechanics CDragon can't show) |

  `changes` holds only the changes of **this** patch (loader diff and patch note lines). A copied document starts with empty `changes`, so the history of an ability is the `changes` of each patch. Today the loader extends the old list on every patch (`_add_changes_champion`). Unvalidated abilities are the input for AI drafts later (Phase 4/6)
- [ ] **Images (decided):**
  - Source: CommunityDragon for all images. Data Dragon only has the client's shop/overview icons and misses recasts and forms (Sion W recast); the spell data names each spell's icon path. Check that sizes are uniform
  - Every patch downloads all images and stores them under a content hash (`VeigarBalefulStrike.3fa2c1.png`). Same image, same name, nothing written; a changed image gets a new name, however often it changes. Documents point to their file, so each patch shows its own image and nothing needs renaming afterwards
  - Images are never deleted, so items removed from the game keep their image in old patches
  - No sprites: they saved requests in the HTTP/1.1 era; a few hundred small icons load fine one by one. `Image` shrinks to a path (no `sprite`, `x`, `y`, `w`, `h`)
  - Stages can have their own image (Sion W recast), falling back to the ability's image
- [ ] Error handling refactor: dead `urllib` excepts, `_retry` swallowing non-HTTP errors, `gather` without `return_exceptions` (orphaned tasks), blocking `requests.get` inside `async` functions, `image` unbound in `_load_rune`
- [ ] The patchloader tests write into the real `src/logs` (e.g. `liandrys_all.log`); mock the loggers like `tests/test_errors.py` does
- [ ] Re-download the 12 zero-byte images
- [x] **Decided: CommunityDragon is the source for numbers, for patches and hotfixes.**
  - Timing (checked for 26.20–26.23): the CDragon folder (`raw.communitydragon.org/<16.x>/`, game version 16.x = patch 26.x) is there on release Wednesday between 07:15 and 09:40 UTC. The wiki patch page exists 1–2 days earlier but is mostly a stub until the night before release; the wiki champion pages lag by an unknown time
  - Content: `DataValues` per spell with stable names (`BaseDamage`, `APRatio`, …, 7 entries = rank 0–6), `mSpellCalculations` with the tooltip formulas (Veigar Q: `TotalDamage = BaseDamage + APRatio * AP`), cooldowns (`cooldownTime`, index 1 = rank 1), mana (`mana`, index 0 = rank 1), missile speeds. `spellTotalTime` looks like a default (1.0 s on many spells), so real animation lengths would need the animation files. Quirks to handle: float noise (`0.44999998`), mana lists with 6 instead of 7 entries (check the indexing), several spells per ability (`AnnieR` + `InfernalGuardian`), unused spells (`Incinerate`)
  - Hotfixes: CDragon rewrites the patch folder in place (Varus' 26.21 hotfix 33 ⇒ 42 is in `16.21`), with no history, so how fast is unknown. Balance hotfixes are rare (1 in 26.13–26.22). Detection: the wiki hotfix list (as today) plus the build number in `content-metadata.json`; a new build triggers a reload and a value diff, so bugfix-only builds change nothing. A wiki hotfix with numbers that CDragon doesn't show yet marks the object "hotfix reported, not in the data yet". Log build numbers with timestamps to learn the delay
  - Riot's official sources: later, they tend to be incomplete
  - Items, summoner spells, runes (checked Sheen, Hextech Gunblade, Ignite, Conqueror, Electrocute): items (`items.cdtb.bin.json`) have named single values (`mDataValues`), calculations (`mItemCalculations`, Gunblade `ActiveDamage = 175 → 253 by level + 0.3 * ap`), stats as fields (`mFlatMagicDamageMod`), icon path and tooltip keys; item actives are spells in `shared.cdtb.bin.json` (`HextechGunbladeSpell`: cooldown, range). Summoner spells are in `shared.cdtb.bin.json` in the champion spell format (Ignite adds a 12th part type, `GameCalculationModified`). Runes (`perks.cdtb.bin.json`) only have named script values (`MinAdaptivePerStack`, `MaxStacks`, …) and no calculations, so their wiki text matters more
  - Mana cost lists have 6 entries starting at rank 1 (Veigar Q 30–50 in the wiki), value lists 7 starting at rank 0
- [x] **Decided: build order, one type at a time, each complete:** (1) champions first load, checked against the test group fixtures; (2) champions patching, tested by loading an old CDragon patch and patching forward (e.g. 16.20 → 16.21 with Varus' hotfix), with the test group fixtures (converted to names and `amount`) as the hand-made part; (3) summoner spells; (4) items incl. actives; (5) runes. Patching right after the first load, because it is the point of this phase and tests today's decisions early
  - ✅ Translator (`loader/cdragon.py`), named values in formulas (`values`, `q.Name`; pets read them from their owner's view), all test group champions use names. Their `values` keep the numbers each fixture was built with
  - Later in step 1: refresh the fixture `values` from the loader (current patch) and update the expectations, each checked against the wiki. Known changes: Annie Q (80–240 ⇒ 80–260) and W (70–250 ⇒ 70–230), Vayne W (6–10 % / 50–110 ⇒ 4–10 % / 40–100), Urgot R cooldown (120/90/60 ⇒ 100/85/70), Annie E cooldown (not in `cooldownTime`, find it)
  - Levels 19/20 (check in the practice tool): interpolations continue past 18 by default (`mScalePastDefaultMaxLevel` only appears as `false`; the wiki agrees for Darius' bleed). Breakpoint formulas have no such flag and continue too, unconfirmed: Tibbers' HP (fixture 4000 at 19/20, translator 4350/4700), Annie E's movement speed (fixture stops at 18, CDragon continues)
- [x] **Decided: champion base stats come from CDragon** (checked against `Module:ChampionData` for Veigar, Annie, Darius, Vladimir, Riven). The `CharacterRecord` has `baseHPModifiable`, `hpPerLevelModifiable`, `baseArmorModifiable`, `baseMR`, `baseDamageModifiable`, `attackSpeedModifiable`/`attackSpeedRatioModifiable`/`attackSpeedPerLevelModifiable`, `attackRangeModifiable`, `baseMoveSpeedModifiable`, `basicAttack.mAttackDelayCastOffsetPercent` (+ `…AttackSpeedRatio` = `windup_modifier`; Vladimir uses `mAttackCastTime`/`mAttackTotalTime` instead), `mAdaptiveForceToAbilityPowerWeight`, `primaryAbilityResource.arType`. Regeneration is per second (the wiki shows per 5 s); champion regen fields and the simulation now use per second too. Item flat regen stats must be per second as well (Phase 3 items). Every champion has a windup (`mAttackDelayCastOffsetPercent` or `mAttackCastTime`/`mAttackTotalTime`, checked for 27); a missing one is an error. The simulation uses `windup_modifier` (wiki formula, see docs/league-mechanics.md); the old test fixtures had the scraper's value / 100 and are fixed
  - Hashed fields are FNV-1a hashes of the lowercased field name, so they are the same for every champion. The mana fields are unknown to CDragon's hash list (`CommunityDragon/Data`, `hashes.binfields.txt`); guessed and confirmed: `{726ee5cd}` = `arBaseModifiable`, `{6216bf7b}` = `arPerLevelModifiable`, `{c4ab3550}` = `arBaseStaticRegenModifiable`, `{3a509002}` = `arRegenPerLevelModifiable` (could be contributed to CDragon)
  - Missile speed: the `missileSpeed` field is outdated (Veigar 1100); the real one is `mSpell.mMissileSpec.movementComponent.mSpeed` of the basic attack spell (Veigar 1500, Vayne 2000, as in the wiki). Probably the same for ability missiles (Veigar Q: wiki 2200, `missileSpeed` 1200)
  - Melee/ranged from `purchaseIdentities` (Nidalee lists both, base form first), adaptive type from `mAdaptiveForceToAbilityPowerWeight` (missing = physical). Hashed fields are read by name or hash (`bin_field`), so they keep working once CDragon knows the names
  - Data Dragon stays for the champion list and `maxrank`. The resource type stays Data Dragon's `partype` (our `ResourceType` uses its texts) `Module:ChampionData` is loaded every run as a cross-check; a mismatch goes to the log (the wiki has errors too: Annie's HP per level is -10 there)
- [x] **Decided: the wiki is read through its data templates, not its HTML.** Every ability has a template (`Template:Data_Veigar/Baleful_Strike?action=raw`) with fields (`damagetype`, `spellshield`, `projectile`, `targeting`, `cast time`, `notes`); `Module:ChampionData/data` has every champion (incl. `adaptivetype`), `Module:ItemData/data` every item. Used for notes and editor suggestions; removes most of the fragile HTML scraping. Check whether the patch page works as raw text too
- [ ] PBE preview (V1, after the base loader): CDragon mirrors the PBE (`pbe/`, e.g. 16.24 while 26.23 is live) in the same format, about two weeks ahead. Load it as a provisional next patch, clearly marked, replaced on release. Gives time for bigger reworks and shows users what is coming. PBE values still change, and some never ship
- [ ] Dash and leap travel times (Nidalee's Pounce lands at the cast today), e.g. from CommunityDragon's spell data or other sources
- [ ] Animation locks after the cast time (e.g. Riven Q uncanceled vs. canceled) from real data instead of assumptions. Then `Lock` can tell an animation from a cast time: item actives can't be used during a cast time, but during a pure animation (wiki)
  - Cast times are not reliable in CDragon: three fields (`spellCastTime`, often a default 0.25 and once -2.0; `mCastTime`; `castFrame`, a frame of the animation at 30 fps) that disagree with each other and with the wiki (Darius Q 0.75 in the wiki, 0.25 in `spellCastTime`). Decided: `cast_time` stays hand-owned, the editor suggests the wiki template's `cast time` and shows the three CDragon fields. Phase 4: a few practice tool checks or the CommunityDragon Discord could tell what each field means
  - Animation lengths are in the `.anm` files, which CDragon does not serve (404); the animation graph (`animations/skin0.bin.json`) only names the file per clip. Reading them needs the local game files (WAD archives)
- [ ] Fresh load into the new format
- [ ] `extra = forbid` for the hand-entered containers (Ability, Passive, Pet) so typos fail; needs a fresh load or an `$unset` of the old `effects` in the DB first

## Phase 4: Admin side complete

- [ ] **Rule editor** for the new format: rules (trigger, conditions, actions), buffs, stats, inputs, stages, pets, `Custom`. Values reference the named values from the loader. The current editor still has only the old effect components
- [ ] **Data checks on PUT:** run each changed ability once in a mini simulation (dummy target, all ranks), reject with a clear message on error
- [ ] Editor: field for `Champion.adaptive_type` (only if the loader can't scrape it)
- [ ] Editor: show save errors (400/422); update `originalChampion` after saving; load `/enum` once and `provide` it
- [ ] PUT without changes should not be an error (today: 400)
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
