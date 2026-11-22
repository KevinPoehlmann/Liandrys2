# League mechanics reference

The general game rules the simulation has to follow, collected from the League wiki (live state, read 2026-11-19). Champion and item details live in the fixtures, not here.

Each section ends with **Simulation:** what the code does today. ⚠ marks a gap or a deviation. Points marked *(unverified)* came from parts of a wiki page that could not be read word for word; check them before building on them.

Wiki base URL: `https://wiki.leagueoflegends.com/en-us/<Page>`

---

## Ticks
Pages: Tick_and_updates (edited 2024-11, marked "needs clean-up")

- The server ticks every **0.033 s** (33 ms), i.e. 30.30 per second. Under load ticks can take longer (the game slows down).
- Anything that would end in the middle of a tick happens on the **next whole tick**: a 0.25 s cast time takes 8 ticks = 0.264 s.
- Some things only update every n-th tick: buffs every 8 ticks (0.264 s) and health regen every 16 ticks (both from the Damage_over_time page; the Tick page itself lists no cadences). The phase of these cadences runs from game start.

**Simulation:** `TICK_SECONDS = 0.033`; `to_ticks` rounds every duration up to whole ticks. ✓ ⚠ No update cadences; effects that wait for the next buff update (Ignite's first tick) happen right away, because the game clock's phase is unknown.

## Champion stats and level growth
Pages: Champion_statistic

- Stat at level n: `base + bonus + g × (n − 1) × (0.7025 + 0.0175 × (n − 1))`, g = growth per level. Level 1→2 adds 0.72 g, 17→18 adds 1.28 g, 19→20 adds 1.35 g.
- Growing stats: AD, armor, MR, HP, HP regen, mana, mana regen, attack speed. Everything else is base-only or bonus-only.
- Growth counts as **base** for AD/armor/MR/HP (`bonus_ad` = total − base excludes it). Attack speed growth counts as **bonus** attack speed (see below).

**Simulation:** `get_base_stat` uses exactly this formula. ✓

## Damage and mitigation
Pages: Damage, Armor, Magic_resistance, Armor_penetration, Magic_penetration

- Three damage types: physical (armor), magic (MR), true (not mitigated).
- Multiplier for resistance R: `100 / (100 + R)` if R ≥ 0, else `2 − 100 / (100 − R)` (at most 2×, i.e. −100 armor = 1.5×).
- Order, per damage type:
  1. flat resistance reduction (stacks additively, can go below 0)
  2. percent resistance reduction (stacks multiplicatively, skipped if R ≤ 0)
  3. percent penetration (stacks multiplicatively, skipped if R ≤ 0); bonus-only percent pen (Lord Dominik's style, K'Sante R, Yasuo R) applies to bonus resistance only
  4. flat penetration / lethality (stacks additively, can't push below 0, skipped if R ≤ 0)
- Reduction changes the target's resistance for everyone; penetration only changes the value used for this attacker's damage.
- Base and bonus resistance are tracked separately (for bonus-only pen). The page contradicts itself on how flat reduction splits between them; its examples split proportionally.
- Damage amplification and reduction (percent, flat) exist; they stack multiplicatively with resistances, but the page gives **no fixed order** *(unverified)*.

Damage modifiers (page Damage_modifier, marked outdated):
- A modifier changes the whole damage instance by a percent or flat value, optionally only for one damage type. It is not extra damage.
- **Damage dealt** modifiers stack **additively** (since V26.09, before multiplicatively). **Damage received** modifiers stack **multiplicatively**, also with the reduction from armor/MR.
- Flat reduction: some before resistances (Fizz passive, Leona, Amumu, Guardian's Horn), some after (Bone Plating, Warden's Mail); never against true damage; a DoT is reduced per tick. *(unverified)*
- Ignite and Smite are unaffected by damage modifiers. Some amplifiers deal their bonus as a separate damage instance (Zed R, Illaoi E). *(unverified)*

**Simulation:** `Character._calculate_damage` applies percent pen, then flat pen, then clamps at 0. Percent pen stacks multiplicatively (`MULTIPLICATIVE_STATS`). ⚠ No resistance reduction yet. ⚠ When it comes, the clamp at 0 is wrong: a negative resistance from reduction must stay negative and use the negative formula. ⚠ No base/bonus split for bonus-only pen. Damage amplification: stat `damage taken percent` on the target, multiplied after resistances, sources multiply, true damage excluded (Hemoplague). ✓ ⚠ No flat amplification and no damage reduction yet.

## Damage tags
Pages: Damage (marked "substantially incomplete" by the wiki)

The engine tags each damage instance; tags imply default properties:

| Engine tag | Meaning | Default properties |
|---|---|---|
| BasicAttack | basic attacks | life steal, on-hit |
| ActiveSpell | most abilities and item actives | triggers ability effects (spell effects) |
| AOE | area damage | usually penalized vs single target |
| Periodic | DoTs, channels | does not break sleep |
| Proc | secondary damage (on-hit, spell effects) | does not chain further effects |
| Indirect | not directly caused by the player | rare |
| Pet | summoned units, credited to the owner | |
| Item | item and summoner spell damage | |
| OnHit | all on-hit effects | |

Untagged damage is called "default damage" (executes, zero-value instances). Per-instance properties include `ApplyLifesteal`, `ApplyOmnivamp`, `ApplyCritical`, `TriggerOnHitEvents`, `RespectDodge`, `EnableKill`.

**Simulation:** `DamageType` uses the tooltip names (Basic, Ability, Area, Proc, …), close to but not identical with the engine tags (e.g. no Periodic, Item, OnHit). ⚠ Only the first tag reaches `ProcessedDamageProperties`. Nothing reacts to tags yet. Decided: the final tag list follows the **engine tags**; switch when the first item/rune reacts to them.

## Triggers (on-action effects)
Pages: On-action_effects (incomplete), On-damage_effects (stub), Attack_effects/Abilities, Ability_effects (redirect from Spell_effects)

The game's trigger categories:

| Category | Fires when | Examples |
|---|---|---|
| on-attack | the windup completes (some: when the attack starts) | Kayle passive waves, Rageblade, Runaan's |
| on-cast | an ability is cast, **some at the start of the cast time, others at the end** | Annie passive, Lucian passive, Sheen gaining its buff |
| on-hit | together with the attack's damage (on-hit formulas see the target before the hit) | BotRK, Sheen proc, Thornmail (on being hit) |
| on-damage | any damage instance lands (also blocked damage; not if invulnerable, dodged or blinded) | Darius bleed, Conqueror, Black Cleaver, Liandry's |
| on-spell | an ability lands ("on-hit for abilities") | Luden's |
| on-cc / on-immobilization | a CC is applied | Aftershock, Volibear Q |
| on-crit | an attack crits | Tryndamere E cooldown |
| on-death | a kill, sometimes an assist or own death | Triumph, Master Yi passive refund |
| on-heal / on-shield | a heal or shield is given | Aery, Ardent Censer |

- **Spell effects** (Liandry's, Luden's, Rylai's, Arcane Comet, Dark Harvest, …) trigger on any ability damage, **including attacks that count as abilities**. A second group (Muramana, Shojin, Horizon Focus, …) triggers only on champion ability damage.
- **Attacks that apply on-hit *and* spell effects:** Darius W, Vayne Q, Blitzcrank R passive, Camille Q, Garen Q, Jax W, Nasus Q, Trundle Q, Volibear Q, … (Attack_effects/Abilities).
- Rageblade's phantom hit repeats on-hit effects, not on-attack effects.

**Simulation:** triggers `on_start`, `on_cast`, `on_attack`, `on_hit`, `on_damage_taken` (also when a shield absorbs everything), `on_stack`, `on_interval` work; `on_get_hit` fires together with `on_hit`, from the side of the one hit (the attacker is its `target`); `on_damage_dealt` fires for every damage above 0, from the side of the one who dealt it, and for a pet's damage also for its owner. Every action is a cast instance; rules can be gated per cast instance (`cast_cooldown`, Conqueror's 4 s). `on_cast` fires at the start of the cast time (Spellblade is granted then, and stays if the cast is cancelled). ⚠ No on-spell, on-cc, on-crit, on-death, on-heal/shield. ⚠ The trigger filter only knows slots, not damage tags (needed for spell effects and for "physical damage only" like Black Cleaver).

## Basic attacks and attack speed
Pages: Basic_attack, Attack_speed, Attack_effects

- Attack timer = `1 / attack speed`. It has two phases: windup (attack is executed), then cooldown.
- Melee attacks hit at the end of the windup; ranged attacks launch a missile there.
- Missiles travel at their speed over the distance (the simulation assumes 100 units, `DEFAULT_DISTANCE`). Some accelerate up to a max speed (Veigar R: 500 → 4000 units/s at 4000 units/s², from CommunityDragon); the simulation models that.
- Total attack speed: `base + ratio × (growth bonus + other bonus AS)`; growth uses the level formula. Most champions have ratio = base.
- Cap 3.003 attacks/s, floor 0.2. Some champions change the cap (Bel'Veth, Jinx R, Varus, Hail of Blades, Sion, Zeri, Urgot W fixed at 3.0).
- Windup: `currentWindup = baseWindup + windupModifier × (attackTime × windupPercent − baseWindup)` with `baseWindup = windupPercent / baseAS` (level 1, no bonus AS). With `windupModifier = 1` (default) this is simply `attackTime × windupPercent`.
- Cancelling: a new command during the windup cancels the attack (no damage) and resets the timer. Inside the last tick before the hit the attack can't be cancelled any more. After the hit, everything is free again (the rest of the animation is cosmetic).
- Since V25.24, casting an ability **without cast time** no longer interrupts an attack.
- Attack reset: sets the timer to 0. During a windup it cancels the current attack.
- On-attack effects fire when the windup completes (launch); on-hit effects when the attack hits. Blind, dodge (Jax E, Nilah W) and block (Shen W) prevent the hit.
- Cripple (attack speed reduction) stacks multiplicatively *(unverified)*.

**Simulation:** windup locks the attacker, then abilities may start at once, the next attack waits for the full timer. ✓ `on_attack` fires at the end of the windup, `on_hit` when the damage lands. ✓ Cripple multiplies. ⚠ No attack speed cap/floor. ⚠ Windup ignores `windup_modifier`; also the loader divides the wiki's modifier by 100 ([webscraper2.py:108](../backend/src/server/loader/webscraper2.py#L108)), which looks wrong given a default of 1. ⚠ An attack reset during a windup doesn't cancel the attack (only reachable if a combo casts a reset during a windup).

## Adaptive force
Pages: Adaptive_force

- 1 adaptive force = 0.6 bonus AD or 1 AP. It goes to whichever the champion has more **bonus** of; a tie goes by the champion's adaptive type (physical/magic, listed on each champion's wiki page). Sources: the two shards, Conqueror, Gathering Storm, Absolute Focus, Waterwalking, Jack of All Trades.
- The comparison doesn't count the champion's own passive AD/AP; item passives mostly count (exceptions on the wiki page, e.g. Archangel's, Manamune, Riftmaker). Rabadon's Magical Opus counts, including the part it adds to uncounted sources: Veigar's 10 Phenomenal Evil stacks count as 3 AP through Opus.

**Simulation:** ✓ `Champion.adaptive_type`, adaptive force goes to AD or AP in `get_stat`; the comparison leaves out everything from the champion's passive and abilities. ⚠ Simplified on purpose (owner): all item passives count, and the Opus share of champion sources doesn't. Only matters when bonus AD and AP are nearly equal. Adaptive *damage* (Arcane Comet and Electrocute use a different, per-formula rule) comes with Electrocute.

## Critical strikes
Pages: Critical_strike

- Crit damage 200% (since V26.01; 175% before). Bonus crit damage stacks additively.
- Crit chance stacks additively, max 100%.
- Crits are pseudo-random (failure streak, capped at 5), not independent rolls. Expected value per attack: `1 + chance × (critMultiplier − 1)`.
- Some abilities always crit (Ashe Q, Jhin 4th shot, …), some never (Fiora's first passive attack, …). Ability damage that scales with crit chance is not a crit.

**Simulation:** ✓ `Action.crit` picks a crit per attack (True/False); without a choice the expected value is used. Only damage with `can_crit` crits (the attack itself, Darius W's bonus; not Vayne Q's bonus, not on-hit damage). ⚠ The UI threshold (pick below e.g. 5 attacks, expected value above) and the probability of k crits with the pseudo-random algorithm are Phase 5. ⚠ No bonus crit damage (Infinity Edge) yet.

## Ability haste and cooldowns
Pages: Haste (redirect from Ability_haste)

- Cooldown: `base × 100 / (100 + haste)`. Haste stacks additively, cap 500.
- Separate ultimate haste and summoner spell haste exist.
- Haste does not shorten static cooldowns (e.g. item passives) unless stated.

**Simulation:** `_cooldown_ticks` uses the formula, plus our per-slot reduction stats. ✓ ⚠ No cap, no ultimate haste.

## Healing, vamp and Grievous Wounds
Pages: Healing, Heal_and_shield_power, Life_steal, Vamp (Omnivamp), Grievous_Wounds

- Healing can't exceed max HP. Max HP gains are not healing.
- Heal and shield power: additive with itself, multiplicative with other heal modifiers. Affects self/outgoing heals, shields and drain; **not** life steal, omnivamp or incoming heals.
- Life steal: % of post-mitigation damage of basic damage (and anything tagged "applies life steal", on-hit item damage). Omnivamp: % of all post-mitigation damage; 33% effectiveness for area/pet/persistent damage against minions and monsters. Neither benefits from heal power.
- Drain (damage-based heals like Vladimir Q/E): benefits from heal power; pre-mitigation drains are calculated before damage modifiers.
- Grievous Wounds: −40% healing and HP regen received, does not stack. Affects all heals including life steal and omnivamp; does **not** affect shields.
- Grievous Wounds from being hit (Thornmail) lands before the attack's life steal, so the triggering attack already heals less (wiki, owner-confirmed). Keep this order when life steal is built.
- Open in the wiki: whether vamp counts damage absorbed by shields.

**Simulation:** heals are capped by missing HP in `_apply_heals`. ✓ Grievous Wounds is a status whose strength is the reduction; the strongest counts, it reduces heals and health regeneration (heal results keep the unreduced value in `raw`). ✓ ⚠ No heal power. ✓ Life steal heals from basic and on-hit damage after the tick's damage (origin `vamp / life steal`). ✓ Omnivamp heals from all damage except Ignite/Smite (summoner spells), origin `vamp / omnivamp`. ⚠ The 33 % omnivamp against minions and monsters for area/pet/persistent damage comes with minions. `vamp` on a damage action is a per-rule vamp.

## Resources and regeneration
Pages: Health_regeneration, Mana, Mana_regeneration, Energy, Ability_resource, Grievous_Wounds

- Health and mana regenerate in 0.5 s intervals (the Damage_over_time page: every 16 engine loops = 0.528 s, which is `to_ticks(0.5)`). Disabled while the value equals the maximum. The stat is "per 5 seconds"; each interval restores a tenth (energy: "5 energy per 0.5 seconds").
- Base regen grows per level like the other growing stats. Flat and "% base regen" bonuses are additive, 1:1: regen = base × (1 + % base) + flat. Multiplicative regen modifiers stack additively with each other.
- Some mana sources depend on missing or maximum mana (Meditation, Crest of Insight, Howling Abyss).
- Energy: 200 maximum (Shen 400, Akali up to 300), doesn't grow; 50 per 5 s; only Crest of Insight raises it. Restored by abilities (Lee Sin, Shen, Zed, Akali, Kennen, Ambessa) and Presence of Mind.
- Only mana and energy are real casting costs. Fury, Rage, Heat, Flow, Grit, Ferocity, Blood Well, Crimson Rush and the like are empowerment or consumable stacks (buffs with stacks in our model).
- Regen counts as healing only for healing modifiers: Grievous Wounds reduces it by 40%; heal and shield power, Revitalize etc. don't affect it.
- No explicit in-combat/out-of-combat timer for regen; some sustain only works out of combat (Garen, Warmog's).

**Simulation:** `Character.regenerate` catches up every 16 ticks when the clock moves (`Simulation._set_clock`), counted from tick 0, so regeneration never keeps the simulation alive. Health, mana and energy (max from the champion's mana fields) start full. Results of type `Regen` with a `resource`. ✓ ⚠ No in-/out-of-combat, no level-up mana restore, no missing/max-mana regen sources.

## Shields
Pages: Shield, Spell_shield

- A shield absorbs damage **after** resistances.
- Several shields: the one that **expires soonest** absorbs first (exceptions: Camille's Adaptive Defenses and Morgana's Black Shield go first).
- Types: normal (all damage), magic-only, physical-only.
- Heal and shield power increases shields; Grievous Wounds doesn't reduce them.
- Some effects destroy shields before dealing damage (Blitzcrank R, Rell, executes).
- A spell shield is not a damage shield: it blocks a hostile ability (all instances within 0.1 s), but secondary effects (stacks, refunds) still happen. It takes priority over normal shields.

**Simulation:** `_use_shields` absorbs post-mitigation damage; `_apply_shields` keeps the shields sorted by expiry, so the one that expires first absorbs first. ✓ ⚠ No shield types (every shield absorbs everything), no spell shields, no Adaptive Defenses/Black Shield priority.

## Crowd control and tenacity
Pages: Crowd_control, Types_of_Crowd_Control, Tenacity

| CC | Move | Attack | Cast | Tenacity |
|---|---|---|---|---|
| Airborne (knock-up/back/pull) | no | no | no | no |
| Stun, Suspension | no | no | no | yes |
| Suppression | no | no | no | no |
| Stasis | no | no | no | no |
| Sleep (breaks on damage) | no | no | no | yes |
| Root | no | yes | partly (no dashes) | yes |
| Silence | yes | yes | no | yes |
| Polymorph | slowed | no | no | yes |
| Disarm | yes | no | yes | yes |
| Taunt / Berserk / Charm / Flee | forced | forced/no | no | yes |
| Blind | yes | misses | yes | yes |
| Cripple | yes | slower | yes | yes |
| Slow | slower | yes | yes | yes |
| Ground | partly | yes | partly | yes |
| Nearsight, Drowsy | – | – | – | no |
| Kinematics | partly | yes | yes | no (always bound to an area) |

- Tenacity: `duration × (1 − T)`, minimum 0.3 s, fixed at application. Stacking in three groups: multiplicative inside a group, additive across groups, capped at 100%.
  - A: items/runes (Mercury's, Sterak's, Wit's End, …, Chemtech Blight)
  - B: Cleanse, Milio, mode adjustments (ARAM)
  - C: Garen passive, Brittle (−30%)

**Simulation:** `check_action_delay` blocks by CC; `_apply_tenacity` keeps the 0.3 s minimum. ✓ Tenacity comes from items and buffs (Cleanse) and stacks as one multiplicative product (`MULTIPLICATIVE_STATS`); `get_stat(TENACITY_P)` is the tenacity itself. ⚠ No stacking groups yet. ⚠ No Root/Polymorph/Charm/Flee in `StatusType`.

**Cleanse** (wiki): removes all disables except airborne, nearsight, suppression and stasis, plus summoner spell debuffs (Ignite's damage, Exhaust); Ignite's Grievous Wounds stays (Cleanse and Ignite notes; the owner remembers it differently, not testable in the practice tool). Usable during CC except suppression and stasis. 75% tenacity for 3 s, 240 s cooldown. **Simulation:** action `Cleanse(target, statuses, buff_tags)` with the lists in the fixture, buff `tags`, ability flag `usable_during_cc`. ✓

## Movement speed and slows
Pages: Movement_speed

- `(base + flat) × (1 + Σ additive %) × Π(1 + multiplicative %) × (1 − strongest slow)`, then soft caps:
  - 415–490: `R × 0.8 + 83`; above 490: `R × 0.5 + 230`
  - below 220: `110 + R × 0.5`; below 0: `110 + R × 0.01`
- Only the **strongest** slow counts. Slow resist reduces each slow: `slow × (1 − resist)`.

**Simulation:** `Character._get_movespeed`: (base + flat) × (1 + additive %) × (1 − strongest slow), then `soft_cap_movespeed`. ✓ ⚠ No multiplicative bonuses, no slow resist.

## Damage over time
Pages: Damage_over_time (no patch stated, edited 2026-10)

- Common intervals: 1 s, 0.5 s, 0.25 s, rarely 0.125 s. The engine runs every ~0.033 s (like our `TICK_SECONDS`).
- **First tick:** some DoTs tick immediately on application, others only after the first interval. Defined per effect.
- Most DoT debuffs can be refreshed; whether they stack is per effect (Darius and Briar bleed up to 5, Skarner up to 3, Brand explodes at 3).
- Persistent (engine: Periodic) damage is "generally restrictive" for triggers and does not break sleep.
- Tether DoTs end when the tether breaks; area DoTs when the target leaves the area (some linger briefly).
- Buffs/debuffs are internally updated every 8 engine loops (0.264 s); health regen every 16 loops (0.528 s).
- **Ignite** (checked in game by the user): 5 ticks of 14–105 true damage, every 1.056 s (= 32 engine loops). The first tick comes 0–0.264 s after the cast (at the next stat update), so the last one lands at about 4.2–4.5 s, well before the 5 s debuff ends. There is **no** tick at the end. The wiki's "last tick at 5.28 s" contradicts its own 5 ticks (5.28 s would be a 6th tick).
- So DoTs differ in both ends: Darius' bleed has no tick on application but one at the end, Ignite the other way round.
- Not on the page: final tick at expiry, snapshot vs. live stats, rhythm on refresh. Our rules (tick at expiry, keep the rhythm) come from the user's game knowledge.

**Simulation:** DoTs are buffs with `interval` and `on_interval` rules. The rhythm comes from the first stack, a refresh keeps it, the buff ticks once more at its end, damage is computed live at each tick. `tick_on_apply` and `tick_on_end` choose the two ends per buff. Ignite's first tick comes 0–0.264 s after the cast in the game (next stat update); we tick right away, because the phase of that update rhythm depends on the game clock.

## Cast time and channels
Pages: Cast_time, Channel (both marked partly outdated)

- Cast time is a lockout: no moving, no attacks, no other abilities or item actives (a few exceptions, Flash usually allowed). Most are 0.25 s, the range is 0.1–1.25 s.
- **It cannot be interrupted**, except by death. What happens after it happens regardless of the caster's state.
- **Cooldown and cost start after the cast time** by default. Exceptions start at cast start (wiki list: Jinx W, K'Sante Q, Kayle R, Kindred R, Senna Q, Syndra R, Thresh Q, Veigar W, Viego, Yasuo Q, Yone Q/W, Yunara, Zeri Q). Darius R is not on that list, although its ability page says "starts on cast"; the ability page wins.
- The effect lands at the end of the cast time, except a list of abilities whose effect comes earlier (Akali Q at 3/4 of the cast, Jhin R shots at 0.2 s, Gwen Q/E, Xin Zhao R, …).
- Some cast times scale with attack speed or windup (Jinx W, Kai'Sa W, Yasuo/Yone Q, Zeri Q, Smolder Q, …); some can be done while moving (Kayle, Samira R, Swain R, …).
- Channels are different: the caster is occupied, the channel can be interrupted by stun, airborne, silence, suppression and so on (or by the caster's own action, e.g. Katarina R), interruption usually doesn't refund the cooldown. Cooldown start for channels is not stated.

**Animation locks:** the wiki's cast time is the lock for most abilities. Some abilities lock longer than their cast time unless the animation is canceled (Riven's Q with a move command), and the wiki has no numbers for that; CommunityDragon's `spellTotalTime` looks like a default value. Riven's Q uses an input `riven_q_cancel` (default: not canceled) with assumed lock times, listed in the ability's `assumptions`. Real numbers are a Phase 4 topic.

**Simulation:** `cast_time` is a formula (so attack-speed scaling works) and locks the caster until the rules land. ✓ `cooldown_starts_on_cast` covers the exception list. ✓ ⚠ No effects before the end of the cast time (rule delays only go forward). ⚠ No channels (Katarina R, Karthus R): needs interrupt handling once the enemy acts in the combo.

## Summoned units (pets)
Pages: Champion_summoned_units (wiki marks it outdated, last updated V14.22)

- Kinds: clones (Shaco, LeBlanc, Wukong, Neeko: inherit item stats and passives, their attacks are not ability damage), minions (Tibbers, Yorick ghouls, Zyra plants, Heimerdinger turrets, Malzahar voidlings, …; own stats, sometimes scaling with the owner), traps (Teemo, Caitlyn, Jhin, Nidalee, Shaco boxes; ability damage), structures/terrain (Anivia W, Azir sun disc), and "markers" (Zed shadows, Syndra spheres, Azir soldiers) that are not real units.
- Damage is credited to the owner. Tibbers' aura and Heimerdinger's turrets deal ability damage. Control: commanded (Tibbers, Daisy, clones), autonomous (most minions), uncontrollable (Fiddlesticks effigy, Lissandra R clones).
- Some pet attacks apply life steal (Tibbers, Daisy, Voidlings — the wiki marks this unexpected).

**Simulation:** autonomous minions ✓ (own actor `blue.<pet>`, attacks the owner's enemy until it expires, uses the owner's penetration — confirmed for Tibbers). ⚠ Pets can't be attacked or die yet; no commands (recast/move); no clones; pet life steal not modelled. Damage results carry the pet's id; crediting it to the owner is the frontend's job (team = first part of the id).

## Still to read
From the wiki's 133 "Gameplay elements" pages, these look relevant later:

- **Named item effect**: unique item passives don't stack (two of the same item, shared names). Needed before items.
- **Attack effects** (parent page) and **On-action effects/Abilities Grouped by Consistency With On-Cast Effects**: which on-cast effects fire at the start and which at the end of the cast time.
- **Spell shield**, **Invulnerability**, **Untargetability**: what still lands.
- **Dash**, **Blink**, **Projectile**: action timing.
- **Stack**, **Stacking**, **Aura**, **Tether**: buff shapes we may not cover yet.
- **Takedown**, **Kill**: execute and reset mechanics (2v2).
- **Ability resource**, **Energy**, **Manaless**: costs (mana is not simulated yet).
