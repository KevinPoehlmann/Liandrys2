# Ability system (Phase 2 design)

The reference for the Phase 2 rebuild. It records what we decided and why. Details that only show up while building are listed at the end as open points.

## Goals

- One vocabulary for everything a champion, item or rune can do, so the simulation, the editor and the Phase 4 data checks each know every action exactly once.
- Time lives in the simulation. Characters hold state and react to events.
- Weird mechanics go through a small escape hatch instead of growing the generic system forever.

## Data model

### Containers

Abilities and passives stay separate, because they carry different metadata. They share the same inner shape.

```python
Ability:
    name, cost, cooldown, cast_time, recharge   # as today
    cooldown_starts_after: str | None            # a buff name: the cooldown starts when that buff ends (Vayne Q, Darius W)
    cooldown_starts_on_cast: bool = False        # default: the cooldown starts after the cast time (Darius Q); True for Darius R
    stages: list[Stage]                          # the active part; 1 for almost everything, Riven Q has 3
    rules: list[Rule]                            # the passive part, e.g. Vayne W; inactive at rank 0
    stats: list[StatModifier]                    # the passive part, e.g. Darius E armor pen; inactive at rank 0
    buffs: list[Buff]

Stage:
    recast_window: str
    outcomes: list[str] = []  # how the cast can land, e.g. Darius Q ["blade", "handle", "miss"]; the first is the default
    rules: list[Rule]         # trigger is implicitly "this stage is cast"

Passive:
    name
    rules: list[Rule]
    stats: list[StatModifier]   # always active
    buffs: list[Buff]
```

Items and runes use the same `Ability` (actives) and `Passive`. Buff definitions live in the ability or passive that uses them.

### Rule

```python
Rule:
    trigger: Trigger | None     # None inside a Stage
    filter: TriggerFilter | None
    outcome: str | None         # inside a Stage: runs only for this outcome; None = always
    conditions: list[Condition]
    actions: list[Action]
    delay: str = "0"            # the rule's actions land together after delay + travel time
    speed: str = "0"            # missile (start) speed, 0 = instant
    acceleration: str = "0"     # units/s², 0 = constant speed (Veigar R: 500 -> 4000)
    max_speed: str = "0"        # 0 = no cap
    cooldown: str = "0"         # Sheen 1.5 s, Electrocute; replaces static_cooldown
    cast_cooldown: str | None   # per container, cast instance and target: "4" (Conqueror), "inf" = once (Electrocute)
```

A buff created while an event is handled does not react to that same event. Otherwise Final Hour's stealth, which ends `on_cast`, would end on the very Q cast that created it.

`on_stack` is the exception: it belongs to the buff itself, so it also fires for the stacks that create the instance. A condition decides whether anything happens (Silver Bolts at 3 stacks).

Rules run in list order, one after the other. Buff changes (`ApplyBuff`, `RemoveBuff`) take effect immediately, so the next rule's conditions already see them. Damage, heals, shields and status go into the queue. The order is part of the meaning (see Annie and Darius below). Across containers the order is: champion passive, Q, W, E, R, items, runes, then active buffs.

The outcome is chosen per action in the combo (`Action.outcome`), not in the scenario, because two Qs in one combo can land differently. It is a rule field and not a condition, because conditions compare numbers; this way a typo is caught when the stage is loaded. A miss is just an outcome no damage rule listens to; the cooldown still runs.

`delay` and `speed` sit on the rule, not on each action: everything a missile carries (damage, stun, a stack) lands together. Components with different timings go into separate rules.

```python
Trigger:
    on_cast          # any ability cast (Annie, Sheen)
    on_attack        # basic attack launched
    on_hit           # basic attack lands (on-hit)
    on_damage_dealt  # any damage lands (Conqueror, Electrocute, Veigar, Black Cleaver)
    on_get_hit       # hit by a basic attack (Thornmail)
    on_damage_taken  # any damage taken, also if a shield absorbs all of it (Annie E)
    on_start         # once when the simulation starts (Annie's starting Pyromania stacks)
    on_interval      # periodically while a buff is active (DoTs, auras)
    on_stack         # this buff gained stacks, whatever applied them (Vayne W from attacks and E)

TriggerFilter:
    source: list[ActionType] | None    # e.g. ["q"]: Final Hour reacts only to Tumble casts
    # more keys when needed (e.g. damage sub type for Black Cleaver)

Target:
    self             # whoever owns the rule (for buff rules: the buff's source)
    target           # the counterpart of the event or the cast
    bearer           # whoever carries the buff (only inside buff rules)

Triggers without a counterpart (`on_stack`, `on_interval`) use the bearer as `target`. So `target_max_hp` in Vayne's Silver Bolts reads the max HP of the enemy carrying the stacks.

Condition:
    actor: self | target | bearer
    key: str            # formula, e.g. "missing_hp_percent", "stacks_hemorrhage"
    comparison: Comparison
    value: str
```

### Actions

| Action | Purpose |
|---|---|
| `Damage`, `Heal`, `Shield`, `Status` | today's components, plus `target`. `delay`/`speed` move to the rule, `duration`/`interval` become a buff |
| `ApplyBuff(buff, target, stacks)` | give a buff or add stacks |
| `RemoveBuff(buff, target, stacks)` | consume "next attack" buffs, reset stacks; with `stacks` only that many (Tibbers' enrage loses one per attack) |
| `ResetAttack` | Vayne Q, Riven Q, Darius W |
| `ModifyCooldown(slot, amount \| reset \| at_most)` | Nidalee: Hunt resets R, Pounce drops to 1.5 s; no slot = the rule's own ability |
| `Summon(pet)` | creates a pet defined in the ability's `pets` (Annie R) |
| `Custom(function, args)` | escape hatch, see below |

`target` is an enum: `self`, `target`, `bearer` (buff rules), `pet` (the owner's active pet; the action is skipped while there is none), `owner` (inside pet rules), `enemy` (the enemy champion; for auras).

**Auras** are buffs on their source with an interval, whose rules hit `enemy` (Tibbers' Flame Aura, Sanguine Pool). Debuffs are buffs on the target itself (Darius' bleed, Ignite). The difference matters for untargetable targets.

In JSON every action has the same shape as today's polymorphic models, with all fields in `props`:

```json
{"type_": "ApplyBuff", "props": {"buff": "silver_bolts", "target": "target", "stacks": "1"}}
{"type_": "Damage", "props": {"target": "bearer", "amount": "...", "dmg_type": ["Proc damage"], "dmg_sub_type": "True", "vamp": 0.0}}
{"type_": "ResetAttack", "props": {}}
```

The full example is the Vayne fixture in `backend/src/tests/static/test_group/champions/vayne.json`.

### Buff

A buff is a named definition. At runtime a character carries **instances** of it.

```python
Buff:
    name: str                  # valid Python identifier, unique per champion/item/rune
    duration: str = "0"        # 0 = unlimited
    max_stacks: int = 1        # 0 = unlimited (Veigar's Phenomenal Evil)
    refresh: bool = True       # does a new stack reset the duration?
    interval: str = "0"        # for on_interval
    tick_on_apply: bool = False  # first interval tick right on application (Ignite)
    tick_on_end: bool = False    # extra tick when the buff ends off-rhythm (Darius bleed)
    windup_cancel: list[ActionType] = []  # slots that may start during the windup of an attack made with this buff; the hit still lands (Darius W -> Q)
    stats: list[StatModifier]  # active on the bearer
    rules: list[Rule]          # active while the buff is

BuffInstance (runtime only):
    name, source, bearer, stacks, start, end
```

Counters are buffs too: Annie's 4 casts, Vayne's 3rd hit and Conqueror's 12 stacks are all buffs with stacks. DoTs are buffs with `interval` and an `on_interval` rule.

```python
StatModifier:
    stat: Stat
    formula: str
    mode: flat | percent
    conversion: bool = False   # sees only stats without conversions (Vladimir)
```

Besides the normal stats there are per-slot stats such as `q cooldown reduction`. That way a buff can change another ability without touching it (Vayne R shortens Q's cooldown), and ultimate haste fits the same pattern.

## Runtime

### Who does what

- **Simulation:** owns time. It schedules events in the queue and dispatches them when their tick comes.
- **Character:** owns state (buff instances, stacks, HP). When told about an event, it answers with the actions of the rules that match. It never looks at the clock by itself.

### Buff instances in the queue

When `ApplyBuff` creates an instance, the simulation schedules its interval events and its end. On a refresh it moves `end` and schedules the missing interval events. The instance remembers its current `end`. An end event that belongs to an outdated `end` is ignored, so old queue entries never need to be searched and removed.

With `tick_on_end`, a buff with an interval also ticks at its end, even if the last regular tick was just before (Darius bleed). With `tick_on_apply`, the first tick comes right on application (Ignite: 5 ticks over 5 s, none at the end).

Implementation: only the next interval tick is in the queue (`BuffTick`). The instance remembers it (`next_interval`); after a refresh the next tick is computed again and an event that no longer matches is ignored. Interval rules run before buff ends on the same tick, so the end tick still sees the stacks. An interval buff without a duration raises `NotImplementedError` (it would tick forever).

Inside any buff rule (`on_interval`, `on_stack` and triggered ones like `on_hit`), `stacks` are the stacks of that buff on its bearer, and `bearer` is the character carrying it.

Example, Darius' bleed:

1. Tick 40: Darius' basic attack lands. Damage is applied, then `on_hit` is sent to Darius.
2. His passive rule returns `ApplyBuff(hemorrhage, target)`.
3. The simulation creates the instance on Red (`stacks 1, start 40, end 190`) and schedules intervals at 78, 115, 153, 190 and the end at 190.
4. Tick 78: the interval rule returns `Damage`. Darius evaluates the formula, Red takes the damage.
5. Tick 100: the next hit adds a stack and refreshes `end` to 250. Interval events up to 250 are scheduled.
6. Tick 250: last tick and end. The instance is removed.

### Order inside one tick

1. **Evaluate** raw values (attacker). The attacker may read the target, read-only.
2. **Apply** damage, heals, shields and status (defender): resistances, shields, heal caps, tenacity.
3. **Fire triggers** (`on_hit`, `on_damage_dealt`, ...). Buffs applied here count from the **next** hit on.

So the hit that applies a Black Cleaver stack does not profit from it, as in League. Abilities that shred armor *before* their own damage use a small `delay` on the damage.

Mitigation order: flat reduction → percent reduction → percent penetration → flat penetration.

## Formulas

### Variables

The formula namespace is built by the simulation and is separate from the `Stat` enum. The enum stays as it is, because its values are keys in the stored item data.

| Group | Variables |
|---|---|
| own stats | `ad`, `base_ad`, `bonus_ad`, `ap`, `bonus_ap`, `armor`, `bonus_armor`, `mr`, `bonus_mr`, `max_hp`, `base_hp`, `bonus_hp`, `current_hp`, `missing_hp`, `missing_hp_percent`, `max_mana`, `base_mana`, `bonus_mana`, `attackspeed`, `bonus_attackspeed` (incl. growth per level), `lethality`, `armor_pen_percent`, `magic_pen`, `magic_pen_percent`, `ability_haste`, `crit_chance`, `crit_damage` (2.0 = 200 %), `bonus_crit_damage`, `movespeed`, `is_champion` (0 for pets), `ranged` (grows as needed) |
| target stats | the same names with a `target_` prefix, generated by a loop |
| context | `level`, `rank`, `rank_q` … `rank_r`, `stacks` (inside a buff: its own stacks), `stacks_<buff>`, `target_stacks_<buff>`, `elapsed_<buff>` (share of the buff's duration that has run out, 0–1), `cooldown`, `cooldown_multiplier`, `elapsed` |
| damage-triggered rules | `damage` (post-mitigation, including what a shield absorbed), `health_damage` (what reached health), `physical`/`magic`/`true` and `tag_<tag>` (0/1 per damage tag: `tag_basic`, `tag_proc`, `tag_pet`, `tag_ability`, `tag_on_hit`, ...), in `on_damage_dealt` and `on_damage_taken` |
| named values | Riot's names from the loader-owned `values` of the container (`BaseDamage`, `TotalDamage`), resolved at the container's rank; another slot's with a prefix (`q.TumbleCDReduction`, `passive.dAbilityStacks`) at that slot's rank. A named value is itself a formula and may use other names; cycles are an error. Our own variables come first |

**Scenario inputs** are things the simulation can't know and the user ticks or enters: `terrain` (1 = there is a wall behind the target, Vayne E), starting stacks (Veigar Q kills). They are plain variables in the namespace. Tests set them directly; the UI comes in Phase 5.

Implemented in `simulation/formula.py`. `bonus_<stat>` is total minus base, so buffs count as bonus too. `stacks_<buff>` and `elapsed_<buff>` of an inactive buff are 0 (a buff without duration has `elapsed_` 0 too; typos in buff names are a job for the Phase 4 data checks). `current_mana` and `bonus_attackspeed` wait until a champion needs them. `eval` runs with empty builtins plus `min`, `max`, `floor`, `by_rank`, `by_level`.

All formulas are evaluated by the source (the champion that owns the rule or buff).

`rank` is the rank of the ability that defines the rule or buff, so Vayne's Silver Bolts use her W rank even when E applies the stack. A condition is evaluated from its actor's point of view: `stacks_silver_bolts` with `actor: bearer` reads the bearer's stacks. Python builtins like `min` and `max` are available (`eval` adds them).

`HpScaling` is removed. "8% of the target's max HP" is written as `0.08 * target_max_hp`. This also covers formulas where the percentage sits inside the formula (Veigar R, Riven R2), and base damage plus %HP in one component.

### Lookups

```python
by_rank(50, 80, 110)          # one value per rank; length must equal maxrank
by_level(10, 12, 14, ...)     # one value per level; exactly 20 values (top laners reach 20)
```

Each table lives inside its call, so a formula can mix several: `by_rank(50, 80, 110) + by_rank(1.0, 1.1, 1.2) * ad`. The scraper always writes this form and expands breakpoint tables ("at level 1/6/11/16") to 20 values. Linear step formulas are no longer written.

## Escape hatch

```python
@custom_action("zed_death_mark")
def zed_death_mark(ctx: ActionContext, percent: str) -> list[Action]:
    stored = ctx.target.buff("death_mark").data["damage"]
    return [Damage(amount=f"{stored} * ({percent})", target=Target.TARGET)]
```

- The function gets a read-only context and **returns normal actions**. It changes nothing directly, so the simulation stays in charge of time and order.
- A decorator registers it by name. `/enum` serves the names, and the editor shows a dropdown plus fields for `args`.
- Logic lives in code, numbers stay data in `args`.
- Phase 4 check: the name exists and `args` match the signature. Every custom function gets its own test.
- **Rule:** use `Custom` only when a single champion needs a new concept. When a second one needs it, it becomes a real building block. The test group must work without `Custom`.

## Examples

**Sheen**
```yaml
buffs:
  - name: spellblade, duration: "10"
    rules:
      - trigger: on_hit
        actions: [Damage(amount: "base_ad", target: target), RemoveBuff(spellblade, self),
                  ApplyBuff(spellblade_cooldown, self)]
  - name: spellblade_cooldown, duration: "1.5"
rules:
  - trigger: on_cast, filter: [q, w, e, r], condition: stacks_spellblade_cooldown == 0
    actions: [ApplyBuff(spellblade, self)]
```
The cooldown is a buff because it starts with the empowered hit, not with the rule that grants the buff; an unused buff runs out without a cooldown (owner).

**Annie passive** (the stun belongs to the first ability that *lands*, so it sits in the landing rules of Q/W/R)
```yaml
inputs: [pyromania_start, default 4, 0–4]
buffs:
  - name: pyromania, max_stacks: 4
    rules:
      - trigger: on_stack
        conditions: [bearer stacks_pyromania == 4]
        actions: [ApplyBuff(pyromania_energized, self), RemoveBuff(pyromania, self)]
  - name: pyromania_energized
rules:
  - trigger: on_start
    conditions: [self pyromania_start > 0]
    actions: [ApplyBuff(pyromania, self, "pyromania_start")]
# in each stage of Q/W/R (E only the first rule), in this order:
  - conditions: [self stacks_pyromania_energized == 0]
    actions: [ApplyBuff(pyromania, self)]
  - conditions: [self stacks_pyromania_energized == 1]
    actions: [Status(Stun, target), RemoveBuff(pyromania_energized, self)]
  - actions: [Damage(...)]
```
The ability that brings the 4th stack doesn't stun: `pyromania_energized` comes from the `on_stack` rule, which runs after the stun check in the same tick.

**Darius passive**
```yaml
buffs:
  - name: hemorrhage, duration: "5", max_stacks: 5, interval: "1.25"
    rules:
      - trigger: on_interval
        actions: [Damage(amount: "... * stacks", target: bearer)]
  - name: noxian_might, duration: "5"
    stats: [ad: flat "..."]
rules:
  - trigger: on_hit
    actions: [ApplyBuff(hemorrhage, target, stacks: "5 if stacks_noxian_might else 1")]
  - trigger: on_hit
    conditions: [target stacks_hemorrhage == 5]
    actions: [ApplyBuff(noxian_might, self)]
```

**Black Cleaver**
```yaml
buffs:
  - name: carve, duration: "6", max_stacks: 6
    stats: [armor: percent "-0.05 * stacks"]
rules:
  - trigger: on_damage_dealt (physical)
    actions: [ApplyBuff(carve, target, 1)]
```

**Vladimir passive**
```yaml
stats:
  - ap: flat "0.03333 * bonus_hp", conversion: true
  - hp: flat "1.6 * ap", conversion: true
```

## Test group

Fixtures in `tests/static`, not the DB or the editor. One test per combo with the expected damage. A building block is done when its member works.

| Who | Covers |
|---|---|
| Veigar | stacks as input (Q kills) vs. stacks from hits (passive), damage by missing HP (R), delayed damage (W) |
| Annie (+Tibbers) | counter ("after 4 casts"), shield on self, `on_get_hit`; Tibbers as a design check for pets |
| Darius | stacking DoT with max and duration, buff granted at max stacks, next attack buff, cooldown reset |
| Vayne | every 3rd hit, attack reset, timed buff (R) |
| Riven | recasts (stages), charges consumed by the next attack, transformation (R) |
| Vladimir | stat conversion without an endless loop, self-heal |
| Items/runes | Sheen, Thornmail, Blade of the Ruined King (current-health on-hit, life steal, melee/ranged), The Collector (threshold execute, crits), Hextech Gunblade (item active, omnivamp), Conqueror, Electrocute |

Later, by entering champions with new mechanics (e.g. Gnar, Nidalee), we see whether the system is extensible.

## Open points

- **Trigger list (from docs/league-mechanics.md, Triggers):** build when the test group needs them:
  - `on_damage_dealt` is built (The Collector): it fires for every damage above 0 from the side of the one who dealt it, with `damage`/`health_damage`; a pet's damage fires only the pet's rules. `on_get_hit` is built (Thornmail): it fires with every `on_hit`, so also for fully shielded attacks and for pets' attacks.
  - Missing categories: on-spell (ability lands; Luden's), on-cc (Aftershock), on-crit, on-death/takedown (2v2), on-heal/shield (Aery).
  - The trigger filter needs damage tags and damage types besides slots: spell effects react to ability damage (including Darius W and Vayne Q attacks), Black Cleaver to physical damage.
  - `on_cast` fires at the start of the cast time (Sheen's wiki notes; owner agreed it fits everywhere). `on_attack` still fires at the end of the windup.
- **Pets (built):** a pet is its own actor, not a buff of its owner.
  - **Actor ids:** `Actor` is a validated string: the team first, then the path to the unit (`blue`, `red`, `blue.tibbers`, `blue.ghoul#2`). Later `blue.top` and `blue.top.tibbers` fit the same pattern. The owner is stored on the pet, not read from the id.
  - **Definition:** an ability lists `pets` (name, duration, stat formulas, attack, passive). Stat formulas use the rank of the summoning ability and read the owner with `owner_` (`owner_ap`). The pet's passive is the normal `Passive` model; the owner also knows the pet's buffs, so Annie's stun can enrage Tibbers.
  - **Behaviour:** `PetCharacter` (simulation/pet.py) reuses `Character` and replaces only stats, attack speed (no ratio: bonus attack speed scales the base), windup, the attack rule and penetration (the owner's, confirmed for Tibbers). On summon its `on_start` rules fire and it attacks the owner's enemy on its own until it expires. On expiry its buffs end, including debuffs it put on others.
  - **Expiry:** rules of an expired pet don't run anymore, so an attack still in flight misses (the owner's decision; not checked in game).
  - **Tibbers:** stats from the wiki's templates (health per level from level 6, armor/MR `5 * level`, the rest by R rank). Enrage is a buff with 5 stacks, one removed per attack; the attack speed formula indexes a list with the remaining stacks (1.736 → 0.739, then 0.625). The aura is a buff on Tibbers hitting `enemy` (ticks every 0.25 s, 180 ticks); 1v1 assumes the enemy stays within 350 units. Windup 40 % from CommunityDragon's own Tibbers character (`annietibbers`: 30 % shifted by +0.1; the wiki has none, 20 % was assumed before). Left out: the enrage movement speed, Ghosted, Recovery, Revenge.
  - **Enrage duration:** the wiki's 3 s is rounded; in ticks the enrage lasts until the 5th attack starts (92 ticks = 3.036 s), and an attack starting on a buff's end tick still gets the buff (the owner's observation in game). It stays time-based, so a stun on Tibbers would let it run out earlier.
  - **Not yet:** the enemy attacking or killing the pet, recast/moving (Annie R stage 2), Tibbers' revenge on Annie's death (`on_death`), clones that copy the owner.
- **End of the simulation (built):** the backend simulates until the last effect, at most 60 s after the start of the last action (`MAX_SECONDS_AFTER_LAST_ACTION`; no endless effect is known yet). The response carries `last_action_tick` and `deaths` (actor → tick at which its health first reached 0); the simulation goes on after a death so the overkill stays visible. The frontend shows 10 s after the last action, with "+10 s" and "All" buttons, and marks deaths with a dashed line. Pet results count for their team (first part of the actor id).
- **`bearer`:** introduced for Vayne W, confirmed with Darius (`on_interval` uses the bearer as `target`). Triggered buff rules now also get the bearer.
- **Percent penetration from several sources:** armor and magic pen percent stack multiplicatively, see `MULTIPLICATIVE_STATS`. Percent stats are stored as fractions (0.3, not 30); the loader already divides by 100.
- **`Displace(distance)`:** Vayne E pushes the target 475 units back, which changes the travel time of later projectiles. Build it once the distance comes from the request (Phase 5); today it is always 0.
- **Vayne simplifications:** the wall stun uses the full knockback time as delay (a closer wall would be earlier); the Q dash can be shortened by terrain (minimum unknown, we use the full dash).
- **Scraper or manual entry?** The old data had 75/127/179/231/283 for Vayne's wall damage (really 75/127.5/180/232.5/285) and Vayne R's bonus AD as true damage. Check when we get to the scraper (Phase 3).
- **Night Hunter** (Vayne passive, bonus movement speed while facing an enemy) is left out for now. It is not irrelevant: the Q dash time uses `movespeed`, and items may scale with movement speed. Probably a scenario input ("facing the enemy") later.
- **Not modelled for Vayne:** Silver Bolts resetting on a new target (irrelevant in 1v1).
- **Damage tags:** decided to follow the engine tags from the wiki's Damage page (BasicAttack, ActiveSpell, AOE, Periodic, Proc, Pet, Item, OnHit, …) when the first item/rune reacts to tags; see docs/league-mechanics.md. Until then: `dmg_type` is a list of the wiki's damage tags (Aatrox Q is ability *and* area damage), defaulting to `["Ability damage"]`. The wiki's "Spell damage" is the old name for "Ability damage". The wiki's per-damage properties (`ApplyLifesteal`, `ApplyOmnivamp`, `TriggerOnHitEvents`) are not stored; the simulation derives them from the tags. Rare exceptions (Aatrox passive: proc damage with lifesteal) get handled when a test needs them.
- **Extra tags on attacks:** Vayne's Q-empowered attack is tagged basic *and* ability damage. For now the bonus damage of Tumble and Crippling Strike carries both tags, so life steal heals from it (owner tested Vayne Q in game); the attack's own damage stays basic. Planned solution for the whole attack: a buff field `attack_dmg_type: list[DamageType] = []`. When an attack is created, it adds the tags of the attacker's own active buffs (only buffs that set the field; target buffs never count). Build it when an item/rune reacts to the difference (e.g. Liandry's); nothing in the test group does. Darius W is the same case (the whole attack is also ability damage); that a spell shield blocks all of it is a Darius-specific rule, deferred too.
- **Trigger filters:** only `source` so far. Add keys when a test group member needs them (Black Cleaver: physical damage only).
- **Inputs (decided):** containers (passive, ability, later items and runes) declare `inputs` (name, default, min, max, description). The request's scenario overrides the defaults; unknown names or values out of range are errors. Formulas read inputs by name (`terrain` on Vayne E, `pyromania_start` on Annie's passive). The UI can build its fields from the declarations later.
- **Conversions (built):** a modifier with `conversion: true` is evaluated while all conversion modifiers are switched off, so Vladimir's two bonuses don't feed each other. Percent modifiers (`mode: percent`, Rabadon) still raise NotImplementedError.
- **`cooldown` (built):** formula variable with the cooldown of the formula's slot in seconds, after haste and per-slot reduction. Vladimir's Crimson Rush stack comes with a rule `delay: cooldown` after each Transfusion. `cooldown_multiplier` is the factor alone (Riot's `CooldownMultiplier`, e.g. Miss Fortune's Love Tap refund); a `cooldown` formula never uses it, since the Character applies it on top.
- **Damage amplification (built):** stat `damage taken percent` on the target, applied after resistances; several sources multiply. True damage is not amplified (wiki, Hemoplague).
- **Costs (built):** `cost` + `cost_resource` (none / health / mana / energy) are checked when the cast starts and paid when it ends (an interrupted cast costs nothing; the payment is a `PayCost` rule put in front of the stage's rules). The action `PayCost(resource, amount)` also pays during an effect (Tides of Blood's charge). Results have the type `Cost` and a `resource`. Without enough resource the action waits for regeneration; a cost that can never be paid (more than the maximum, no regeneration, wrong resource) is an error. A health cost can't kill (Dr. Mundo). Open idea for the frontend round: report in the response which action waited and how long, since silent waiting changes the combo.
- **`Lock(duration, exceptions)` (built):** the owner can't attack or cast, except the listed slots (Sanguine Pool: summoners and items; the Tides of Blood charge also allows W). Reuses the windup lock.
- **`Untargetable` (built):** a status; only debuffs already on the target keep ticking (the rule comes from a buff whose bearer is the target). Everything else from the enemy misses: attacks, abilities, delayed bursts and auras.
- **`slowed_while` (built):** while one of the listed buffs is on the bearer, the buff's time runs at `rate`; the end is recomputed (rounded up to whole ticks) whenever such a buff starts or ends. Crimson Rush drains at 25 % in Sanguine Pool and while charging Tides of Blood; stasis comes with Zhonya's.
- **Channels:** rules start at the end of the cast time, so Tides of Blood is a `Lock` for the charge time (an ability input) with rules delayed by the charge. Q and R interrupting the charge are not modelled: the next action in the combo starts at the release. The bolts fly at 4000, so a Hemoplague cast at the release lands first and amplifies them.
- **Default distance (decided):** 100 units, close enough for melee attacks; projectiles still have travel time. Real distances come with Phase 5.
- **Summoner spells (built):** `Character(..., summonerspells=[...])` puts them in the slots S1/S2 like abilities at rank 1; summoner haste instead of ability haste; silence doesn't block them. Not passed in from the route yet (Phase 2 list). Ignite: a debuff on the target (5 ticks every 1.056 s, the first right away) plus the status `Grievous Wounds` for 5 s, so Cleanse can later remove the damage while the healing reduction stays (wiki). Cleanse (built): buffs have `tags` (Ignite's debuff is a `summoner_debuff`); the action `Cleanse(target, statuses, buff_tags)` removes the listed status types and tagged buffs, the lists live in the data so QSS or Mikael's can differ; abilities with `usable_during_cc` ignore stuns, silences and airborne, only suppression and stasis block them. Grievous Wounds isn't in Cleanse's list (wiki); adding it would be one list entry.
- **Origin of results (built):** every result has `origin` (kind / name / buff): champion parts by slot (`ability / Q`, `passive / passive / hemorrhage`, `attack / BA`), summoner spells, items and runes by name (`summoner / Ignite / ignite`), `regen / health`. Pets belong to the ability that summoned them (`ability / R / tibbers_aura`); the result's `actor` tells the pet apart. `Character.origin(slot, buff)` builds it, so nothing new travels through the rules. `source` stays until the frontend uses `origin`. The basic attack slot is `ba` in the request too (renamed from `aa` in the cleanup block).
- **Resources and regeneration (decided, after Vladimir, before Ignite):** HP, mana and energy regenerate over time; Ignite's Grievous Wounds also cuts regeneration.
- **`elapsed`:** seconds since the buff started; available in buff stat formulas and buff rules (Annie's decaying Molten Shield speed). The simulation tells each character the current tick (`current_tick`); the character still never schedules anything itself.
- **Shield and buff:** Molten Shield's reflect buff lasts as long as the shield (3 s) but doesn't end when the shield breaks. Fine in 1v1 (the first hit always meets the shield); with several enemies the buff should end with the shield.
- **Recasts (built):** the next cast of a slot uses the next stage while it is inside that stage's `recast_window` (seconds after the previous cast) and not before its `recast_delay`; a pending recast ignores the cooldown. After the last stage, or when the window runs out, the ability starts over. Only the first stage starts the cooldown (Riven Q: 13 s from the first cast, `cooldown_starts_on_cast`; Riven R: after the buff, `cooldown_starts_after`). Wind Slash doesn't end Blade of the Exile (owner).
- **Snapshot stats (built):** `StatModifier.snapshot` on a buff is evaluated once when the buff is applied or refreshed, without the buff's own snapshot values (Riven R: `0.2 * ad` fixed at the cast).
- **Assumptions (built):** abilities and passives have `assumptions: list[str]` for what we assumed where data is missing, meant to be shown to the user. So far only Riven's Q uses it (cast and animation lock times). Design decisions that hold for everything stay in docs/league-mechanics.md.
- **Veigar (built):** Phenomenal Evil is an unlimited, never-ending buff (`ap = stacks`); the `veigar_stacks` input sets the start stacks through an `on_start` rule. Every ability hit gives a stack through an explicit `ApplyBuff` in the ability's rule (Event Horizon too, without damage); a separate "ability hits" trigger waits for Luden's. Dark Matter's cooldown drops 10 % per 50 stacks in steps (`floor`, owner-confirmed). Missiles can accelerate (`acceleration`, `max_speed` on the rule; `travel_time` in simulation.py). Event Horizon has the outcomes `hit` (stuns as soon as the cage stands) and `miss`. Takedown and Q kill stacks wait for 2v2. Rule delays after a cast time round twice (Dark Matter lands at tick 38 instead of 37), accepted.
- **Items (built with Sheen):** items take the slots I1–I6 in list order, like summoner spells S1/S2. Their passives are collected like abilities (rules, buffs, stats, inputs) with rank 0, and results get the origin `item / <item name> / <buff>`. A `unique` passive is a shared named effect: several items with a passive of the same name give it once (two Spellblade items). Item groups from `limitations` ("Limited to 1 Spellblade item") belong to item picking (ROADMAP Phase 5). `Passive.static_cooldown` is gone; the scraped value stays in `raw_stats`, real cooldowns are rules or buffs.
- **Thornmail (built):** Thorns reflects with `on_get_hit` (damage tag `Reactive damage`, no missile); Grievous Wounds only on champions via the formula variable `is_champion` (0 for pets), Tibbers takes the damage (owner). The owner's penetration counts for the reflect like for any of their damage (Annie's R pen).
- **Blade of the Ruined King (built, replaces Kraken Slayer):** on-hit rules (`on_hit`, `on_get_hit`) run in the same step as the attack, so their formulas see the target before the attack's damage (Mist's Edge reads current health; owner-confirmed); with a delay or speed they are queued as before. Formula variable `ranged` (champions by `range_type`, pets by missile speed) for melee/ranged values, written as `0.06 if ranged else 0.09`. Life steal (`life steal percent`) heals from damage tagged `Basic damage` or the new `On-hit damage` (Mist's Edge, Spellblade), after all damage of the tick, so Thornmail's Grievous Wounds already reduce the first attack; heals have the origin `vamp / life steal`. Clawing Shadows: a new stack refreshes the 6 s, no stacks during the 15 s cooldown, checked on the hit (owner).
- **Crits and The Collector (built):** `Action.crit` (None = expected value `1 + chance × (2 − 1)`, True/False picks it per attack; the UI threshold and the probability of k crits are Phase 5). A damage crits only with `can_crit`: the attack itself and Crippling Strike's bonus yes, Tumble's bonus no (owner; Volibear Q can't either), on-hit damage never. The attack's choice travels with its on-hit rules (`RuleEvent.crit`). Crit damage is a constant 200 % until an item changes it (Infinity Edge). Death is an `on_damage_dealt` rule with `health_damage > 0` (owner: only damage to health executes, not damage to a shield) and the new `Execute` action, which takes the remaining health past shields. Every damage of the owner counts, the bleed too (owner).
- **Item actives (built with Hextech Gunblade):** an item's `active` runs like an ability in the item's slot (I1–I6 by item order, rank 1, like summoner spells); a slot without an active is an error. Results name the active: `item / Hextech Gunblade / Lightning Bolt` (a rule without trigger and outside a buff comes from the cast). The cooldown ignores ability haste; only item haste would shorten it, and nothing gives that today. Actives wait for cast times and locks like abilities (wiki: no item actives during a cast time; see ROADMAP Phase 3 for animations). Omnivamp heals from all damage of the owner except summoner spells (Ignite, Smite), with the origin `vamp / omnivamp`, next to life steal on attacks.
- **Black Cleaver** moved out of the test group (owner): armor reduction and a damage-type trigger filter only add to the format, so they can wait for data entry.
- **Runes (step 1 built):** `Character(..., runes=[...])`; each rune (stat shards too) gets a slot `rune1`–`rune9` (not an action, it only names the container), its passive is collected like an item passive, results get `rune / <name> / <buff>`. `Champion.adaptive_type` (physical/magic) breaks adaptive force ties; see docs/league-mechanics.md. Conqueror step 1: on-hit stacks (melee 2, ranged 1), adaptive force per stack.
- **Cast instances (built with Conqueror):** every action (attack, cast, item active, summoner spell) and every pet attack is a new cast instance (`RuleEvent.cast`). Everything that follows from it shares it: on-hit and on-cast rules, the rules a cast queues, buffs it applies and their interval ticks (a refresh by a new cast takes the new one), on-stack rules, a summoned pet's start rules (Tibbers' aura belongs to R), damage results and the rules they trigger (The Collector's execute). `Rule.cast_cooldown` gates a rule per (owner, rule, cast instance, target).
- **Damage tags in rules (decided instead of filter lists):** damage-triggered rules see `tag_<tag>` variables, so "neither basic nor non-pet proc damage" is the condition `tag_basic == 0` and `tag_proc * (1 - tag_pet) == 0`. A pet's damage always carries `Pet damage` and fires `on_damage_dealt` for its owner too (owner: Tibbers' aura and attacks trigger The Collector). Tibbers' attacks are basic damage (fixture fixed).
- **Conqueror (built):** stacks and the heal are `on_damage_dealt` rules; the heal rule comes first, so the hit that brings the 12th stack doesn't heal yet (owner). Edge case: an on-hit part of that same hit (a second damage result) already heals.
- **Electrocute (built):** new trigger `on_debuff_dealt` (a status or a DoT, i.e. a buff with an interval, applied to an enemy) with the variables `cc`, `dot` and `status_<type>`. The `cast_cooldown` gate is per container (owner, slot, cast instance, target), so Electrocute's damage and debuff rules give one stack per cast together. New comparisons `Greater or equal` / `Less or equal` pick the damage type (physical only if the AD part is bigger; a tie is magic, wiki). The delayed strike is a buff with one interval tick at its end, because a rule's conditions are checked when it runs, not when it is queued. Tibbers' attacks stack it (pet damage).
- **Urgot W (built):** on-hit comes from the damage tag (owner's idea): basic damage from a rule that isn't itself an on-hit rule applies on-hit (attacks, pets' attacks on their own rules, Purge's shots, later Ezreal Q). New action `Attack(target, amount, can_crit, on_hit_factor, attack_speed)`: an attack an ability makes on its own, with its own cast instance, on-attack and on-hit effects (`on_hit_factor` scales their damage, Purge 0.5). Like a basic attack it starts at once, launches after the champion's windup share of `1 / attack_speed` (on-attack fires then) and flies with the attack missile; a shot in flight still hits after Purge is turned off (owner: shots are modified basic attacks). It doesn't touch the attack timer. `Buff.blocks` lists slots that wait while the buff is active (no manual attacks during Purge). The rank 5 toggle is a recast stage with `recast_window` `inf`; a buff with an interval but no duration ticks until removed; `cooldown_starts_after` with such a buff waits until it is removed. `Action.delay` (seconds after the previous action) lets a combo wait, e.g. Purge for three shots. Urgot's passive is left out (which leg fires depends on facing; possible later with leg cooldown buffs and an input for how many legs face the target).
- **Forms (built with Nidalee):** `Champion.extra_abilities` holds more abilities (`ExtraAbility`: `key`, `rank_from`), placed in the internal slots `x1`–`x9`, so cooldowns, ranks, formulas and origins work per ability (each form has its own cooldowns). `Buff.replaces` (slot -> key) points a key press to an extra ability while the bearer's own buff is active; the request keeps sending Q/W/E/R, the simulation resolves the slot before waiting. `Buff.range_type` overrides melee/ranged (the cougar's attacks have no missile, `ranged` is 0). New action `ToggleBuff`. `Ability.counts_as_cast = False` skips on-cast effects (the form swap doesn't grant Spellblade). The form swap doesn't reset the attack timer (owner); both forms have the same attack speed, the same windup is assumed. Hwei's subcasts fit the same pattern (a short buff that replaces Q/W/E). An extra ability's origin is named by the key it sits on, with its key as the third part: `ability / Q / takedown`, `ability / E / swipe` (owner).
- **Nidalee's Hunt (built):** Javelin Toss and Bushwhack (outcome `hit`, step-in time per cast, from 1.5 s when it is armed) mark the target with `hunted`, `hunted_takedown` and `hunted_pounce`, so the first Takedown (+30 %) and the first Pounce (cooldown at most 3/2.5/2/1.5 s) each use the Hunt once; in human form a Hunt resets Aspect of the Cougar. New formula variable `distance` (the simulation's distance); Javelin Toss grows +45 % per full 155 units (wiki), counted from 525 units (assumption), at most 225 %. Not modelled: Prowl, Pounce's longer range and the Hunt extension.
- **Per-cast and list inputs (built):** `Input.per_cast` inputs are chosen per cast in `Action.params` (Riven's Q cancel, Tides of Blood's charge, Bushwhack's step-in time); the scenario value stays the default for every cast. The cast's rules and the buffs it applies (duration, interval, interval rules) see them. `Input.many` inputs are lists; `Rule.for_each` runs a rule once per value with the variable `each` (Nidalee's traps placed before the fight, later Teemo's shrooms).
- **Last DoT tick:** today it deals the full tick damage. Check whether that matches League.
- **Deferred until a champion needs it:** `on_expire` (Zed R, Sion W), `on_takedown` plus extending a buff's duration (Vayne R +4 s, resets like Darius R; only matters with more than one enemy, so together with 2v2), a free `data` field on buff instances (Zed), more champions than blue/red (2v2).
- **Stat enum cleanup:** pseudo stats like `target's armor` or `units` only serve the scraper. Clean them up when the scraper is changed.
- **Attack timing:** the windup locks the attacker; after it, abilities may start at once (the rest of the animation is skipped), while the next attack waits for the full attack time. Cancelling an attack inside its windup (no damage) is not modelled; a combo's attack always completes. `windup_cancel` is the only exception so far.
