# Ability system (Phase 2 design)

The reference for the Phase 2 rebuild. It records what we decided and why. Details that only show up while building are listed at the end as open points.

## Goals

- One vocabulary for everything a champion, item or rune can do, so the simulation, the editor and the Phase 3 data checks each know every action exactly once.
- Time lives in the simulation. Characters hold state and react to events.
- Weird mechanics go through a small escape hatch instead of growing the generic system forever.

## Data model

### Containers

Abilities and passives stay separate, because they carry different metadata. They share the same inner shape.

```python
Ability:
    name, cost, cooldown, cast_time, recharge   # as today
    cooldown_starts_after: str | None            # a buff name: the cooldown starts when that buff ends (Vayne Q)
    stages: list[Stage]                          # the active part; 1 for almost everything, Riven Q has 3
    rules: list[Rule]                            # the passive part, e.g. Vayne W; inactive at rank 0
    buffs: list[Buff]

Stage:
    recast_window: str
    rules: list[Rule]        # trigger is implicitly "this stage is cast"

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
    conditions: list[Condition]
    actions: list[Action]
    delay: str = "0"            # the rule's actions land together after delay + travel time
    speed: str = "0"            # missile speed, 0 = instant
    cooldown: str = "0"         # Sheen 1.5 s, Electrocute; replaces static_cooldown
```

A buff created while an event is handled does not react to that same event. Otherwise Final Hour's stealth, which ends `on_cast`, would end on the very Q cast that created it.

`on_stack` is the exception: it belongs to the buff itself, so it also fires for the stacks that create the instance. A condition decides whether anything happens (Silver Bolts at 3 stacks).

Rules run in list order, one after the other. Buff changes (`ApplyBuff`, `RemoveBuff`) take effect immediately, so the next rule's conditions already see them. Damage, heals, shields and status go into the queue. The order is part of the meaning (see Annie and Darius below). Across containers the order is: champion passive, Q, W, E, R, items, runes, then active buffs.

`delay` and `speed` sit on the rule, not on each action: everything a missile carries (damage, stun, a stack) lands together. Components with different timings go into separate rules.

```python
Trigger:
    on_cast          # any ability cast (Annie, Sheen)
    on_attack        # basic attack launched
    on_hit           # basic attack lands (on-hit)
    on_damage_dealt  # any damage lands (Conqueror, Electrocute, Veigar, Black Cleaver)
    on_get_hit       # hit by a basic attack (Thornmail, Annie E)
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
| `RemoveBuff(buff, target)` | consume "next attack" buffs, reset stacks |
| `ResetAttack` | Vayne Q, Riven Q, Darius W |
| `ModifyCooldown(slot, amount \| reset)` | Darius R |
| `Custom(function, args)` | escape hatch, see below |

`target` is an enum, not a bool, so pets and 2v2 can be added later.

In JSON every action has the same shape as today's polymorphic models, with all fields in `props`:

```json
{"type_": "ApplyBuff", "props": {"buff": "silver_bolts", "target": "target", "stacks": "1"}}
{"type_": "Damage", "props": {"target": "bearer", "scaling": "...", "dmg_type": ["Proc damage"], "dmg_sub_type": "True", "vamp": 0.0}}
{"type_": "ResetAttack", "props": {}}
```

The full example is the Vayne fixture in `backend/src/tests/static/test_group/champions/vayne.json`.

### Buff

A buff is a named definition. At runtime a character carries **instances** of it.

```python
Buff:
    name: str                  # valid Python identifier, unique per champion/item/rune
    duration: str = "0"        # 0 = unlimited
    max_stacks: int = 1
    refresh: bool = True       # does a new stack reset the duration?
    interval: str = "0"        # for on_interval
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

Like today's `_apply_dot`, a buff with an interval also ticks at its end, even if the last regular tick was just before.

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
| own stats | `ad`, `base_ad`, `bonus_ad`, `ap`, `bonus_ap`, `armor`, `bonus_armor`, `mr`, `bonus_mr`, `max_hp`, `bonus_hp`, `current_hp`, `missing_hp`, `missing_hp_percent`, `max_mana`, `attackspeed`, `lethality`, `armor_pen_percent`, `magic_pen`, `magic_pen_percent`, `ability_haste`, `crit_chance`, `movespeed` (grows as needed) |
| target stats | the same names with a `target_` prefix, generated by a loop |
| context | `level`, `rank`, `rank_q` … `rank_r`, `stacks` (inside a buff: its own stacks), `stacks_<buff>`, `target_stacks_<buff>` |

**Scenario inputs** are things the simulation can't know and the user ticks or enters: `terrain` (1 = there is a wall behind the target, Vayne E), starting stacks (Veigar Q kills). They are plain variables in the namespace. Tests set them directly; the UI comes in Phase 5.

Implemented in `simulation/formula.py`. `bonus_<stat>` is total minus base, so buffs count as bonus too. `stacks_<buff>` of an inactive buff is 0 (typos in buff names are a job for the Phase 3 data checks). `current_mana` and `bonus_attackspeed` wait until a champion needs them. `eval` runs with empty builtins plus `min`, `max`, `by_rank`, `by_level`.

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
    return [Damage(scaling=f"{stored} * ({percent})", target=Target.TARGET)]
```

- The function gets a read-only context and **returns normal actions**. It changes nothing directly, so the simulation stays in charge of time and order.
- A decorator registers it by name. `/enum` serves the names, and the editor shows a dropdown plus fields for `args`.
- Logic lives in code, numbers stay data in `args`.
- Phase 3 check: the name exists and `args` match the signature. Every custom function gets its own test.
- **Rule:** use `Custom` only when a single champion needs a new concept. When a second one needs it, it becomes a real building block. The test group must work without `Custom`.

## Examples

**Sheen**
```yaml
buffs:
  - name: spellblade, duration: "10"
    rules:
      - trigger: on_hit
        actions: [Damage(scaling: "base_ad", target: target), RemoveBuff(spellblade, self)]
rules:
  - trigger: on_cast, cooldown: "1.5"
    actions: [ApplyBuff(spellblade, self)]
```

**Annie passive**
```yaml
buffs:
  - name: pyromania, max_stacks: 4
rules:
  - trigger: on_cast
    conditions: [self stacks_pyromania == 4]
    actions: [Status(Stun, target), RemoveBuff(pyromania, self)]
  - trigger: on_cast
    actions: [ApplyBuff(pyromania, self, 1)]
```

**Darius passive**
```yaml
buffs:
  - name: hemorrhage, duration: "5", max_stacks: 5, interval: "1.25"
    rules:
      - trigger: on_interval
        actions: [Damage(scaling: "... * stacks", target: bearer)]
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
  - ap: flat "bonus_hp / 30", conversion: true
  - bonus_hp: flat "ap * 1.6", conversion: true
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
| Items/runes | Sheen, Thornmail, Kraken Slayer, The Collector (threshold execute), Black Cleaver, Conqueror, Electrocute |

Later, by entering champions with new mechanics (e.g. Gnar, Nidalee), we see whether the system is extensible.

## Open points

- **`bearer`:** introduced for Vayne W. Check it again with Darius, where `on_interval` has no counterpart at all.
- **`Displace(distance)`:** Vayne E pushes the target 475 units back, which changes the travel time of later projectiles. Build it once the distance comes from the request (Phase 5); today it is always 0.
- **Vayne simplifications:** the wall stun uses the full knockback time as delay (a closer wall would be earlier); the Q dash can be shortened by terrain (minimum unknown, we use the full dash).
- **Scraper or manual entry?** The old data had 75/127/179/231/283 for Vayne's wall damage (really 75/127.5/180/232.5/285) and Vayne R's bonus AD as true damage. Check when we get to the scraper (Phase 4).
- **Night Hunter** (Vayne passive, bonus movement speed while facing an enemy) is left out for now. It is not irrelevant: the Q dash time uses `movespeed`, and items may scale with movement speed. Probably a scenario input ("facing the enemy") later.
- **Not modelled for Vayne:** Silver Bolts resetting on a new target (irrelevant in 1v1).
- **Damage tags:** `dmg_type` is a list of the wiki's damage tags (Aatrox Q is ability *and* area damage), defaulting to `["Ability damage"]`. The wiki's "Spell damage" is the old name for "Ability damage". The wiki's per-damage properties (`ApplyLifesteal`, `ApplyOmnivamp`, `TriggerOnHitEvents`) are not stored; the simulation derives them from the tags. Rare exceptions (Aatrox passive: proc damage with lifesteal) get handled when a test needs them.
- **Extra tags on attacks:** Vayne's Q-empowered attack is tagged basic *and* ability damage. Planned solution: a buff field `attack_dmg_type: list[DamageType] = []`. When an attack is created, it adds the tags of the attacker's own active buffs (only buffs that set the field; target buffs never count). Build it when an item/rune reacts to the difference (e.g. Liandry's); nothing in the test group does.
- **Trigger filters:** only `source` so far. Add keys when a test group member needs them (Black Cleaver: physical damage only).
- **Annie's stun** must be bound to the damage of the ability, not to the cast.
- **Riven:** when does the cooldown start with recasts? Probably after the last stage or when the recast window runs out, handled in the stage logic.
- **Last DoT tick:** today it deals the full tick damage. Check whether that matches League.
- **Deferred until a champion needs it:** `on_expire` (Zed R, Sion W), `on_takedown` plus extending a buff's duration (Vayne R +4 s, resets like Darius R; only matters with more than one enemy, so together with 2v2), a free `data` field on buff instances (Zed), more actors than blue/red (Tibbers, 2v2).
- **Stat enum cleanup:** pseudo stats like `target's armor` or `units` only serve the scraper. Clean them up when the scraper is changed.
