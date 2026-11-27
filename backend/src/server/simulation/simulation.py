from collections import defaultdict
from dataclasses import replace
import math


from src.server.models.enums import (
    ActionType,
    Actor,
    Comparison,
    DamageSubType,
    DamageType,
    EffectType,
    RuleActionType,
    Stat,
    StatusType,
    Target,
    Trigger,
    TICKRATE,
    to_ticks
)
from src.server.models.request import V1Response, Action
from src.server.models.result import EffectResult, Origin, TickEvent
from src.server.models.rule import (
    ApplyBuffAction, Condition, DamageAction, DamageProps, HealAction, HealProps, RemoveBuffAction,
    ResetAttackAction, Rule, RuleAction, ShieldAction, ShieldProps, StatusAction, StatusProps, SummonAction,
    AttackAction, AttackProps, CleanseAction, ExecuteAction, LockAction, PayCostAction,
    ApplyBuffProps, ModifyCooldownAction, RemoveBuffProps, ToggleBuffAction
)
from src.server.simulation.character import SUMMONER_SLOTS, Character
from src.server.simulation.buff_instance import BuffInstance
from src.server.simulation.components import (
    ProcessedCostProperties,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedShieldProperties,
    ProcessedStatusProperties,
    QueueComponent
)
from src.server.simulation.events import BuffEnd, BuffTick, DashEnd, PetAttackDue, PetExpire, RuleEvent
from src.server.simulation.exceptions import ComboError, DataError, describe, located
from src.server.simulation.formula import FormulaContext, evaluate_formula
from src.server.simulation.pet import PetCharacter

QueueEntry = RuleEvent | BuffEnd | BuffTick | DashEnd | PetAttackDue | PetExpire

# Close enough for any melee attack; projectiles still need travel time (Vladimir's E lands after a Hemoplague cast at its release).
DEFAULT_DISTANCE = 100
# Statuses that are crowd control; Grievous Wounds and untargetability aren't.
CROWD_CONTROL = set(StatusType) - {StatusType.GRIEVOUS_WOUNDS, StatusType.UNTARGETABLE, StatusType.REPLACE}


def travel_time(distance: float, speed: float, acceleration: float = 0, max_speed: float = 0) -> float:
    """Seconds a missile needs; it speeds up until max_speed (Veigar R: 500 -> 4000 units/s)."""
    if speed <= 0:
        return 0
    if acceleration <= 0:
        return distance / speed
    if max_speed > 0:
        speedup_time = (max_speed - speed) / acceleration
        speedup_distance = speed * speedup_time + acceleration * speedup_time ** 2 / 2
        if speedup_distance < distance:
            return speedup_time + (distance - speedup_distance) / max_speed
    # distance = speed * t + acceleration * t² / 2, solved for t
    return (-speed + math.sqrt(speed ** 2 + 2 * acceleration * distance)) / acceleration

# Effects without an end (none known yet) would keep the simulation running forever.
MAX_SECONDS_AFTER_LAST_ACTION = 60
# Rules that trigger each other without a delay never leave their tick; real chains stay far below this.
MAX_RULE_EVENTS_PER_TICK = 1000




class Simulation():
    def __init__(self, blue: Character, red: Character, distance: int = DEFAULT_DISTANCE):
        self.tick: int = 0
        self.distance: int = distance
        self.queue: dict[int, list[QueueEntry]] = defaultdict(list)
        self.effect_list: list[TickEvent] = []
        self.last_action_tick: int = 0
        self.deaths: dict[Actor, int] = {}
        self.casts: int = 0
        # (owner, rule, cast instance, target) -> tick from which the rule may trigger again for that cast (cast_cooldown)
        self.cast_gates: dict[tuple, float] = {}
        self.attack_factors: dict[int, float] = {}  # cast instance of an Attack action -> its on_hit_factor
        self.rule_events_in_tick: tuple[int, int] = (0, 0)  # (tick, rule events run in it so far)
        self.actors: dict[Actor, Character] = {
            Actor.BLUE: blue,
            Actor.RED: red
        }



    def do_combo(self, combo: list[Action]) -> V1Response:
        self._start()
        for i, action in enumerate(combo):
            self.do_action(action, i)
        self._process_remaining_queue()
        return V1Response(
            tick_rate=TICKRATE,
            damage=round(self.actors[Actor.RED].damage_taken),
            ticks=self.tick,
            last_action_tick=self.last_action_tick,
            deaths=self.deaths,
            effect_list=self.effect_list
        )


    def do_action(self, action: Action, index: int | None = None) -> None:
        try:
            self._process_queue()
            action = action.copy(update={"action_type": self.actors[action.actor].resolve_slot(action.action_type)})
            self._check_slot(action)
            self._wait_until_ready(action)
            self._cast(action)
        except Exception as error:
            raise located(error, phase="cast", action_index=index, action_type=action.action_type, actor=action.actor,
                          champion=self.actors[action.actor].name)


    def _check_slot(self, action: Action) -> None:
        character = self.actors[action.actor]
        if action.action_type != ActionType.BA and action.action_type not in character.ability_dict | character.item_slots:
            raise ComboError(f"{character.name} has nothing in slot {action.action_type.value}")


    def _wait_until_ready(self, action: Action) -> None:
        character = self.actors[action.actor]
        self._process_queue()
        earliest = self.tick + to_ticks(action.delay)
        ready = max(earliest, self._ready_tick(character, action.action_type))
        # Events before the action can still change when it is ready, e.g. the hit that consumes Tumble starts Q's cooldown.
        while self.queue and min(self.queue) <= ready:
            q_tick = min(self.queue)
            self.tick = max(self.tick, q_tick)
            self._process_tick(q_tick)
            ready = max(earliest, self._ready_tick(character, action.action_type))
        if math.isinf(ready):
            raise ComboError(f"{action.action_type.value} can never be used: a buff without an end blocks it or its cooldown waits for one")
        self.tick = ready


    def _ready_tick(self, character: Character, slot: ActionType) -> int:
        ready = character.check_action_delay(slot, self.tick)
        return character.resource_ready(slot, ready)


    def _start(self) -> None:
        for actor in list(self.actors):
            self._fire(Trigger.ON_START, actor, self._enemy_of(actor), ActionType.PASSIVE, self.tick)


    def _enemy_of(self, actor: Actor) -> Actor:
        # 1v1: the enemy is the champion of the other team.
        return Actor.RED if actor.team == Actor.BLUE else Actor.BLUE


    def _set_clock(self, tick: int) -> None:
        regenerated = []
        for actor, character in self.actors.items():
            character.current_tick = tick
            regenerated += character.regenerate(tick, actor)
        for regen_tick in sorted({regen_tick for regen_tick, _ in regenerated}):
            self.effect_list.append(TickEvent(tick=regen_tick, result=[result for t, result in regenerated if t == regen_tick]))


    def _cast(self, action: Action) -> None:
        self._set_clock(self.tick)
        start = self.tick
        self.last_action_tick = start
        character = self.actors[action.actor]
        is_attack = action.action_type == ActionType.BA
        cast = self._new_cast()
        if not is_attack and character.counts_as_cast(action.action_type):
            # The cast event comes at the start of the cast time (Spellblade, Riven's Runic Blade).
            self._fire(Trigger.ON_CAST, action.actor, action.target, action.action_type, start, cast=cast)
        action_effect = character.do_action(action, self.tick, self.actors.get(action.target))
        self.tick = action_effect.tick
        for rule_event in action_effect.rule_events:
            rule_event.cast = cast
            self._queue_rule(rule_event, self.tick)
        if action_effect.dash:
            action_effect.dash.cast = cast
            for rule_event in action_effect.dash.rule_events:
                rule_event.cast = cast
            self.queue.setdefault(action_effect.dash.end, []).append(action_effect.dash)
        if is_attack:
            self._fire(Trigger.ON_ATTACK, action.actor, action.target, action.action_type, self.tick, cast=cast)
        if action_effect.windup_cancel:
            # Everything else still waits for the windup; the cancelling slots may start right away.
            character.lock(action_effect.tick, action_effect.windup_cancel)
            self.tick = start


    def _new_cast(self) -> int:
        self.casts += 1
        return self.casts


    def _fire(self, trigger: Trigger, actor: Actor, counterpart: Actor, source: ActionType, tick: int,
              values: dict[str, float] | None = None, cast: int | None = None, damage_factor: float = 1) -> None:
        for event in self._triggered_events(trigger, actor, counterpart, source, values=values, cast=cast, damage_factor=damage_factor):
            self._queue_rule(event, tick)


    def _triggered_events(self, trigger: Trigger, actor: Actor, counterpart: Actor, source: ActionType,
                          crit: bool | None = None, values: dict[str, float] | None = None, cast: int | None = None,
                          damage_factor: float = 1) -> list[RuleEvent]:
        # Rules are collected before any of them runs, so a buff created by this event can't react to it.
        return [
            RuleEvent(rule=rule, slot=slot, owner=self._actor_of(owner), target=counterpart, bearer=actor if buff else None,
                      buff=buff, crit=crit, values=values or {}, cast=cast, damage_factor=damage_factor)
            for rule, slot, owner, buff in self.actors[actor].triggered_rules(trigger, source)
        ]


    def _on_hit_components(self, event: RuleEvent, components: list[QueueComponent], tick: int) -> list[QueueComponent]:
        # Basic damage applies on-hit effects (attacks, Purge's shots, later Ezreal Q), unless it is an on-hit effect itself
        # (Crippling Strike). They run together with the hit, so their formulas see the target before its damage (Mist's Edge).
        if event.rule.trigger in (Trigger.ON_HIT, Trigger.ON_GET_HIT):
            return []
        hits = {(component.target, component.cast) for component in components
                if component.type_ == EffectType.DAMAGE and DamageType.BASIC in component.props.tags}
        on_hit = []
        for target, cast in hits:
            factor = self.attack_factors.get(cast, 1)
            events = (self._triggered_events(Trigger.ON_HIT, event.owner, target, ActionType.BA, crit=event.crit, cast=cast,
                                             damage_factor=factor)
                      + self._triggered_events(Trigger.ON_GET_HIT, target, event.owner, ActionType.BA, cast=cast))
            for triggered in events:
                if self._delay_ticks(triggered) == 0:
                    on_hit.extend(self._run_rule(triggered, tick))
                else:
                    self._queue_rule(triggered, tick)
        return on_hit


    def _fire_damage_triggers(self, results: list[EffectResult], tick: int) -> None:
        for result in results:
            if result.type_ != EffectType.DAMAGE:
                continue
            # Damage absorbed by a shield still counts as taken; an attack without damage (blind) does not.
            if result.raw > 0:
                values = self._damage_values(result)
                self._fire(Trigger.ON_DAMAGE_TAKEN, result.target, result.actor, result.source, tick, values, result.cast)
                # A pet's damage counts for its owner too (The Collector executes with Tibbers).
                dealer = self.actors[result.actor]
                dealers = [result.actor] if dealer.is_champion else [result.actor, self._actor_of(dealer.owner)]
                for actor in dealers:
                    self._fire(Trigger.ON_DAMAGE_DEALT, actor, result.target, result.source, tick, values, result.cast)


    def _fire_debuff(self, event: RuleEvent, target: Actor, tick: int, status: StatusType | None = None, dot: bool = False) -> None:
        if target.team == event.owner.team:
            return
        values = {"cc": int(status in CROWD_CONTROL), "dot": int(dot)}
        values |= {f"status_{kind.name.lower()}": int(kind == status) for kind in StatusType}
        self._fire(Trigger.ON_DEBUFF_DEALT, event.owner, target, event.slot, tick, values, event.cast)


    @staticmethod
    def _damage_values(result: EffectResult) -> dict[str, float]:
        """`damage`, `health_damage`, the damage type and a 0/1 variable per tag (`tag_basic`, `tag_proc`, `tag_pet`, ...)."""
        values = {
            "damage": result.raw - result.mitigated,
            "health_damage": result.value,
            "physical": int(result.damage_sub_type == DamageSubType.PHYSIC),
            "magic": int(result.damage_sub_type == DamageSubType.MAGIC),
            "true": int(result.damage_sub_type == DamageSubType.TRUE),
        }
        return values | {f"tag_{tag.name.lower()}": int(tag in result.dmg_tags) for tag in DamageType}


    def _fire_stack(self, buff: str, buff_rules: list[Rule], slot: ActionType, owner: Actor, bearer: Actor, tick: int,
                    cast: int | None) -> None:
        # on_stack has no counterpart, so the bearer is also the `target`.
        for rule in buff_rules:
            if rule.trigger == Trigger.ON_STACK:
                self._queue_rule(RuleEvent(rule=rule, slot=slot, owner=owner, target=bearer, bearer=bearer, buff=buff, cast=cast), tick)


    def _holds(self, condition: Condition, event: RuleEvent) -> bool:
        owner = self.actors[event.owner]
        context = self._context(event, event.target)
        # The key is read from the actor's point of view, the value is the owner's formula.
        actor = self._resolve_target(condition.actor, event)
        actor_view = replace(context, source=self.actors[actor], target=owner if actor != event.owner else context.target)
        key = evaluate_formula(condition.key, actor_view)
        value = evaluate_formula(condition.value, context)
        match condition.comparison:
            case Comparison.GT:
                return key > value
            case Comparison.LT:
                return key < value
            case Comparison.EQ:
                return key == value
            case Comparison.GE:
                return key >= value
            case Comparison.LE:
                return key <= value


    def _actor_of(self, character: Character) -> Actor:
        return next(actor for actor, candidate in self.actors.items() if candidate is character)


    def _queue_rule(self, event: RuleEvent, tick: int) -> None:
        if event.rule.for_each and "each" not in event.values:
            for value in self.actors[event.owner].scenario.get(event.rule.for_each, []):
                self._queue_rule(replace(event, values=event.values | {"each": value}), tick)
            return
        self.queue.setdefault(tick + self._delay_ticks(event), []).append(event)


    def _delay_ticks(self, event: RuleEvent) -> int:
        context = self._context(event, event.target)
        rule = event.rule
        seconds = travel_time(self.distance, *(evaluate_formula(f, context) for f in (rule.speed, rule.acceleration, rule.max_speed)))
        return to_ticks(evaluate_formula(rule.delay, context)) + to_ticks(seconds)


    def _run_rule(self, event: RuleEvent, tick: int) -> list[QueueComponent]:
        if self._is_gone(event.owner):
            return []  # e.g. an attack still in flight when the pet expires
        if not all(self._holds(condition, event) for condition in event.rule.conditions):
            return []
        if not self._passes_cast_gate(event, tick):
            return []
        components = []
        for action in event.rule.actions:
            components.extend(self._run_action(action, event, tick))
        return components


    def _passes_cast_gate(self, event: RuleEvent, tick: int) -> bool:
        if event.rule.cast_cooldown is None or event.cast is None:
            return True
        # The gate is per container: Electrocute's damage and debuff rules give one stack per cast together.
        key = (event.owner, event.slot, event.cast, event.target)
        if tick < self.cast_gates.get(key, -math.inf):
            return False
        seconds = evaluate_formula(event.rule.cast_cooldown, self._context(event, event.target))
        self.cast_gates[key] = math.inf if math.isinf(seconds) else tick + to_ticks(seconds)
        return True


    def _run_action(self, action: RuleAction, event: RuleEvent, tick: int) -> list[QueueComponent]:
        owner = self.actors[event.owner]
        if getattr(action.props, "target", None) == Target.PET and self._pet_of(event.owner) is None:
            return []  # a rule for the pet while no pet is out
        if self._misses_untargetable(action, event, tick):
            return []
        match action:
            case DamageAction(props=props):
                return [self._damage(props, event)]
            case StatusAction(props=props):
                component = self._status(props, event)
                self._fire_debuff(event, component.target, tick, status=props.status)
                return [component]
            case HealAction(props=props):
                return [self._heal(props, event)]
            case ShieldAction(props=props):
                return [self._shield(props, event)]
            case ApplyBuffAction(props=props):
                bearer = self._resolve_target(props.target, event)
                stacks = int(evaluate_formula(props.stacks, owner.formula_context(event.slot)))
                instance = self.actors[bearer].apply_buff(props.buff, owner, stacks, tick, event.cast, event.values)
                if instance.end is not None:
                    self.queue.setdefault(instance.end, []).append(BuffEnd(bearer=bearer, buff=props.buff, end=instance.end))
                self._schedule_interval(bearer, instance)
                if instance.definition.interval != "0":
                    self._fire_debuff(event, bearer, tick, dot=True)
                self._rescale_slowed_buffs(bearer, tick)
                self._fire_stack(props.buff, instance.definition.rules, instance.slot, self._actor_of(instance.source), bearer, tick, event.cast)
            case RemoveBuffAction(props=props):
                self._check_buff_known(props.buff)
                bearer = self.actors[self._resolve_target(props.target, event)]
                if props.stacks is None:
                    bearer.remove_buff(props.buff, tick)
                else:
                    bearer.remove_stacks(props.buff, int(evaluate_formula(props.stacks, owner.formula_context(event.slot))), tick)
                self._rescale_slowed_buffs(self._actor_of(bearer), tick)
            case PayCostAction(props=props):
                cost = ProcessedCostProperties(resource=props.resource, value=evaluate_formula(props.amount, self._context(event, event.owner)))
                return [QueueComponent(source=event.slot, actor=event.owner, target=event.owner, type_=EffectType.COST, props=cost, origin=self._origin(event))]
            case CleanseAction(props=props):
                bearer = self._resolve_target(props.target, event)
                self.actors[bearer].cleanse(props.statuses, props.buff_tags, tick)
                self._rescale_slowed_buffs(bearer, tick)
            case AttackAction(props=props):
                self._attack(props, event, tick)
            case ToggleBuffAction(props=props):
                bearer = self._resolve_target(props.target, event)
                if props.buff in self.actors[bearer].active_buffs:
                    return self._run_action(RemoveBuffAction(type_=RuleActionType.REMOVE_BUFF,
                                                             props=RemoveBuffProps(buff=props.buff, target=props.target)), event, tick)
                return self._run_action(ApplyBuffAction(type_=RuleActionType.APPLY_BUFF,
                                                        props=ApplyBuffProps(buff=props.buff, target=props.target)), event, tick)
            case ExecuteAction(props=props):
                target = self._resolve_target(props.target, event)
                execute = ProcessedDamageProperties(value=0, flat_pen=0, percent_pen=0, dmg_sub_type=DamageSubType.TRUE,
                                                    execute=True)
                return [QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.DAMAGE,
                                       props=execute, origin=self._origin(event), cast=event.cast)]
            case LockAction(props=props):
                duration = to_ticks(evaluate_formula(props.duration, self._context(event, event.target)))
                owner.lock(tick + duration, set(props.exceptions))
            case ResetAttackAction():
                owner.reset_attack(tick)
            case ModifyCooldownAction(props=props):
                context = self._context(event, event.target)
                at_most = evaluate_formula(props.at_most, context) if props.at_most else None
                owner.modify_cooldown(props.slot or event.slot, tick, evaluate_formula(props.amount, context), props.reset, at_most)
            case SummonAction(props=props):
                self._summon(props.pet, event.owner, tick, event.cast)
            case _:
                raise NotImplementedError(f"Action '{action.type_}' is not supported yet")
        return []


    def _check_buff_known(self, name: str) -> None:
        # Removing a buff that isn't active is fine; one that nobody defines is a typo.
        if not any(name in character.buff_definitions for character in self.actors.values()):
            raise DataError(f"Unknown buff '{name}'")


    def _target_and_context(self, target: Target, event: RuleEvent) -> tuple[Actor, FormulaContext]:
        actor = self._resolve_target(target, event)
        return actor, self._context(event, actor)


    def _context(self, event: RuleEvent, target: Actor) -> FormulaContext:
        # Inside a buff rule, `stacks` and `elapsed` belong to that buff on its bearer.
        bearer = self.actors[event.bearer] if event.bearer else None
        instance = bearer.active_buffs.get(event.buff) if bearer and event.buff else None
        stacks, elapsed = (instance.stacks, bearer.buff_elapsed(instance)) if instance else (0, 0.0)
        context = self.actors[event.owner].formula_context(event.slot, target=self.actors[target], stacks=stacks, elapsed=elapsed)
        return replace(context, event_values=event.values, distance=self.distance)


    def _schedule_interval(self, bearer: Actor, instance: BuffInstance) -> None:
        next_tick = self._next_interval(instance)
        # A refresh can move the next tick; the event at the old tick no longer matches and is ignored.
        if next_tick is not None and next_tick != instance.next_interval:
            instance.next_interval = next_tick
            self.queue.setdefault(next_tick, []).append(BuffTick(bearer=bearer, buff=instance.definition.name, tick=next_tick))


    @staticmethod
    def _next_interval(instance: BuffInstance) -> int | None:
        context = replace(instance.source.formula_context(instance.slot), event_values=instance.values)
        interval = evaluate_formula(instance.definition.interval, context)
        if interval <= 0:
            return None
        # The rhythm is set by the first stack, refreshes keep it. Without a duration it ticks until removed;
        # only the next tick is ever queued, and the simulation's end cap stops it.
        definition, last = instance.definition, instance.last_interval
        k = 0 if definition.tick_on_apply else 1
        while last is not None and instance.start + to_ticks(k * interval) <= last:
            k += 1
        rhythm_tick = instance.start + to_ticks(k * interval)
        if instance.end is None or rhythm_tick <= instance.end:
            return rhythm_tick
        ticks_at_end = definition.tick_on_end and (last is None or instance.end > last)
        return instance.end if ticks_at_end else None


    def _interval_events(self, buff_tick: BuffTick) -> list[RuleEvent]:
        instance = self.actors[buff_tick.bearer].active_buffs.get(buff_tick.buff)
        if instance is None or instance.next_interval != buff_tick.tick:
            return []
        instance.last_interval = buff_tick.tick
        instance.next_interval = None
        self._schedule_interval(buff_tick.bearer, instance)
        owner = self._actor_of(instance.source)
        return [
            RuleEvent(rule=rule, slot=instance.slot, owner=owner, target=buff_tick.bearer, bearer=buff_tick.bearer,
                      buff=buff_tick.buff, cast=instance.cast, values=instance.values)
            for rule in instance.definition.rules if rule.trigger == Trigger.ON_INTERVAL
        ]


    def _attack(self, props: AttackProps, event: RuleEvent, tick: int) -> None:
        # Like a basic attack: it starts now, launches after its windup (on-attack) and flies with the attack missile.
        owner, context = self.actors[event.owner], self._context(event, event.target)
        cast = self._new_cast()
        self.attack_factors[cast] = evaluate_formula(props.on_hit_factor, context)
        attack_speed = evaluate_formula(props.attack_speed, context) if props.attack_speed else owner.get_stat(Stat.ATTACKSPEED_P)
        windup = owner.windup_time(1 / attack_speed)
        damage = DamageAction(type_=RuleActionType.DAMAGE, props=DamageProps(
            target=props.target, amount=props.amount, dmg_type=[DamageType.BASIC],
            dmg_sub_type=DamageSubType.PHYSIC, can_crit=props.can_crit))
        hit = Rule(actions=[damage], delay=str(windup), speed=str(owner.champion.missile_speed))
        self._queue_rule(replace(event, rule=hit, cast=cast), tick)
        target = self._resolve_target(props.target, event)
        self._fire(Trigger.ON_ATTACK, event.owner, target, ActionType.BA, tick + to_ticks(windup), cast=cast,
                   damage_factor=self.attack_factors[cast])


    @staticmethod
    def _crit_factor(crit: bool | None, owner: Character) -> float:
        # A base of 1.0 (Ashe) means crits deal no extra damage, even with bonus crit damage (practice tool, Infinity
        # Edge); her passive still reads that bonus. Without a choice the expected value is used.
        if owner.get_base_stat(Stat.CRIT_DAMAGE) <= 1:
            return 1
        crit_damage = owner.get_stat(Stat.CRIT_DAMAGE)
        if crit is not None:
            return crit_damage if crit else 1
        return 1 + min(owner.get_stat(Stat.CRIT_P), 1) * (crit_damage - 1)


    @staticmethod
    def _life_steal(props: DamageProps, owner: Character) -> float:
        # Life steal heals from basic damage and on-hit damage, not from abilities or reactive damage (Thornmail).
        if {DamageType.BASIC, DamageType.ON_HIT} & set(props.dmg_type):
            return owner.get_stat(Stat.LIFE_STEAL_P)
        return 0


    def _damage(self, props: DamageProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        flat_pen, percent_pen = self.actors[event.owner].get_penetration(props.dmg_sub_type)
        value = evaluate_formula(props.amount, context) * event.damage_factor
        if props.can_crit:
            value *= self._crit_factor(event.crit, self.actors[event.owner])
        processed = ProcessedDamageProperties(
            value=value,
            flat_pen=flat_pen,
            percent_pen=percent_pen,
            dmg_sub_type=props.dmg_sub_type,
            vamp=props.vamp,
            life_steal=self._life_steal(props, self.actors[event.owner]),
            omnivamp=0 if event.slot in SUMMONER_SLOTS else self.actors[event.owner].get_stat(Stat.OMNIVAMP_P),
            # A pet's damage is pet damage (wiki), whatever its own tags are.
            tags=list(props.dmg_type) + ([DamageType.PET] if not self.actors[event.owner].is_champion and DamageType.PET not in props.dmg_type else [])
        )
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.DAMAGE, props=processed,
                              origin=self._origin(event), cast=event.cast)


    def _heal(self, props: HealProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        processed = ProcessedHealProperties(value=evaluate_formula(props.amount, context))
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.HEAL, props=processed, origin=self._origin(event))


    def _shield(self, props: ShieldProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        processed = ProcessedShieldProperties(
            value=evaluate_formula(props.amount, context),
            duration=to_ticks(evaluate_formula(props.duration, context)),
            dmg_sub_type=props.dmg_sub_type
        )
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.SHIELD, props=processed, origin=self._origin(event))


    def _status(self, props: StatusProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        processed = ProcessedStatusProperties(
            type_=props.status,
            duration=to_ticks(evaluate_formula(props.duration, context)),
            strength=evaluate_formula(props.strength, context)
        )
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.STATUS, props=processed, origin=self._origin(event))


    def _resolve_target(self, target: Target, event: RuleEvent) -> Actor:
        match target:
            case Target.SELF:
                return event.owner
            case Target.TARGET:
                return event.target
            case Target.BEARER if event.bearer is not None:
                return event.bearer
            case Target.BEARER:
                raise DataError(f"Target '{target.value}' is only available inside buff rules")
            case Target.PET:
                pet = self._pet_of(event.owner)
                if pet is None:
                    raise DataError(f"{event.owner} has no pet")
                return pet
            case Target.OWNER:
                return self._owner_of(event.owner)
            case Target.ENEMY:
                return self._enemy_of(event.owner)


    def _origin(self, event: RuleEvent) -> Origin:
        # Rules without a trigger and outside a buff come from a cast (an item's active, not its passives).
        return self.actors[event.owner].origin(event.slot, event.buff, active=event.rule.trigger is None)


    def _misses_untargetable(self, action: RuleAction, event: RuleEvent, tick: int) -> bool:
        # Only debuffs already on the target keep ticking (bleed, Ignite); everything else is a new hit and misses:
        # attacks, abilities, delayed bursts and auras (a buff on their source).
        target = getattr(action.props, "target", None)
        if target is None:
            return False
        actor = self._resolve_target(target, event)
        if event.buff is not None and event.bearer == actor:
            return False
        return actor.team != event.owner.team and self.actors[actor].is_untargetable(tick)


    def _rescale_slowed_buffs(self, bearer: Actor, tick: int) -> None:
        character = self.actors[bearer]
        for name, instance in list(character.active_buffs.items()):
            slowing = [entry.rate for entry in instance.definition.slowed_while if entry.buff in character.active_buffs]
            rate = min(slowing, default=1.0)
            if rate == instance.rate or instance.end is None:
                continue
            remaining = (instance.end - tick) * instance.rate
            instance.end = tick + math.ceil(round(remaining / rate, 6))
            instance.rate = rate
            self.queue.setdefault(instance.end, []).append(BuffEnd(bearer=bearer, buff=name, end=instance.end))


    def _is_gone(self, actor: Actor) -> bool:
        character = self.actors[actor]
        return isinstance(character, PetCharacter) and character.expired


    def _pet_of(self, owner: Actor) -> Actor | None:
        pets = [
            actor for actor, character in self.actors.items()
            if isinstance(character, PetCharacter) and not character.expired and character.owner is self.actors[owner]
        ]
        if len(pets) > 1:
            raise NotImplementedError(f"{owner} has several pets, target 'pet' is ambiguous: {pets}")
        return pets[0] if pets else None


    def _owner_of(self, actor: Actor) -> Actor:
        return self._actor_of(self._pet(actor).owner)


    def _pet(self, actor: Actor) -> PetCharacter:
        pet = self.actors[actor]
        if not isinstance(pet, PetCharacter):
            raise DataError(f"{actor} is not a pet")
        return pet


    def _summon(self, name: str, owner: Actor, tick: int, cast: int | None = None) -> None:
        owner_character = self.actors[owner]
        definition, slot = owner_character.pet_definition(name)
        pet = PetCharacter(definition, owner_character, slot)
        pet.current_tick = tick
        pet_id = self._new_pet_id(owner, name)
        self.actors[pet_id] = pet
        lifetime = to_ticks(evaluate_formula(definition.duration, pet.formula_context(ActionType.PASSIVE)))
        self.queue.setdefault(tick + lifetime, []).append(PetExpire(pet=pet_id))
        # The pet's start rules (Tibbers' aura) belong to the summoning cast.
        self._fire(Trigger.ON_START, pet_id, self._enemy_of(pet_id), ActionType.PASSIVE, tick, cast=cast)
        self.queue.setdefault(tick, []).append(PetAttackDue(pet=pet_id))


    def _new_pet_id(self, owner: Actor, name: str) -> Actor:
        pet_id = f"{owner}.{name}"
        number = 2
        while pet_id in self.actors:
            pet_id = f"{owner}.{name}#{number}"
            number += 1
        return Actor(pet_id)


    def _pet_attack(self, pet_id: Actor, tick: int) -> None:
        pet = self._pet(pet_id)
        if pet.expired:
            return
        ready = pet.check_action_delay(ActionType.BA, tick)
        if ready > tick:
            self.queue.setdefault(ready, []).append(PetAttackDue(pet=pet_id))
            return
        target = self._enemy_of(pet_id)
        action_effect = pet.do_action(Action(actor=pet_id, target=target, action_type=ActionType.BA), tick)
        cast = self._new_cast()
        for rule_event in action_effect.rule_events:
            rule_event.cast = cast
            self._queue_rule(rule_event, action_effect.tick)
        self._fire(Trigger.ON_ATTACK, pet_id, target, ActionType.BA, action_effect.tick, cast=cast)
        self.queue.setdefault(pet.cooldowns[ActionType.BA], []).append(PetAttackDue(pet=pet_id))


    def _expire_pet(self, pet_id: Actor, tick: int) -> None:
        # The pet's buffs end with it, also the ones it put on others (an aura on the enemy).
        pet = self._pet(pet_id)
        pet.expired = True
        for character in self.actors.values():
            for name, instance in list(character.active_buffs.items()):
                if character is pet or instance.source is pet:
                    character.remove_buff(name, tick)


    def _process_queue(self) -> None:
        while self.queue and min(self.queue) <= self.tick:
            self._process_tick(min(self.queue))


    def _process_remaining_queue(self) -> None:
        end = self.last_action_tick + to_ticks(MAX_SECONDS_AFTER_LAST_ACTION)
        while self.queue:
            q_tick = min(self.queue)
            if q_tick > end:
                self.queue.clear()
                break
            self.tick = max(self.tick, q_tick)
            self._process_tick(q_tick)


    def _process_tick(self, q_tick: int) -> None:
        try:
            self._run_tick(q_tick)
        except Exception as error:
            raise located(error, phase="effect", tick=q_tick)


    def _run_tick(self, q_tick: int) -> None:
        self._set_clock(q_tick)
        entries = self.queue.pop(q_tick)
        processed = []
        # Interval rules run before buff ends, so the tick at the end still sees the stacks.
        interval_events = [event for entry in entries if isinstance(entry, BuffTick) for event in self._interval_events(entry)]
        arrival_events = [event for entry in entries if isinstance(entry, DashEnd) for event in self._arrival_events(entry, q_tick)]
        rule_events = [entry for entry in entries if isinstance(entry, RuleEvent)] + interval_events + arrival_events
        self._count_rule_events(rule_events, q_tick)
        for event in rule_events:
            try:
                components = self._run_rule(event, q_tick)
                processed.extend(components)
                processed.extend(self._on_hit_components(event, components, q_tick))
            except Exception as error:
                owner = self.actors[event.owner]
                raise located(error, phase="effect", tick=q_tick, origin=self._origin(event), champion=owner.name,
                              rule=owner.rule_position(event.rule))
        if processed:
            self._apply_components(processed, q_tick)
        for expire in [entry for entry in entries if isinstance(entry, PetExpire)]:
            self._expire_pet(expire.pet, q_tick)
        # Like interval rules, an attack that starts on a buff's end tick still gets the buff (Tibbers' 5th enraged attack).
        for due in [entry for entry in entries if isinstance(entry, PetAttackDue)]:
            self._pet_attack(due.pet, q_tick)
        for end in [entry for entry in entries if isinstance(entry, BuffEnd)]:
            self.actors[end.bearer].expire_buff(end.buff, end.end)
            self._rescale_slowed_buffs(end.bearer, q_tick)


    def _arrival_events(self, dash: DashEnd, q_tick: int) -> list[RuleEvent]:
        """The stage's arrival rules without delay run in this tick; delayed ones and other rules reacting to the dash are queued."""
        self._fire(Trigger.ON_DASH_END, dash.owner, dash.target, dash.slot, q_tick, cast=dash.cast)
        now = []
        for event in dash.rule_events:
            if self._delay_ticks(event) == 0:
                now.append(event)
            else:
                self._queue_rule(event, q_tick)
        return now


    def _count_rule_events(self, events: list[RuleEvent], q_tick: int) -> None:
        tick, count = self.rule_events_in_tick
        count = len(events) + (count if tick == q_tick else 0)
        self.rule_events_in_tick = (q_tick, count)
        if count > MAX_RULE_EVENTS_PER_TICK:
            origins = sorted({describe(self._origin(event)) for event in events})
            raise DataError(f"rules keep triggering each other without a delay: {'; '.join(origins)}")


    def _apply_components(self, processed: list[QueueComponent], q_tick: int) -> None:
        evaluated_entries = processed
        effect_results = []
        while evaluated_entries:
            # Damage can cause follow-up effects in the same tick (vamp heals), so repeat until nothing is left.
            follow_ups = []
            for actor, character in self.actors.items():
                new_entries, results = character.take_effects([entry for entry in evaluated_entries if entry.target == actor], q_tick)
                follow_ups += new_entries
                effect_results += results
            evaluated_entries = follow_ups

        self.effect_list.append(TickEvent(
            tick=q_tick,
            result=effect_results
        ))
        self._record_deaths(q_tick)
        self._fire_damage_triggers(effect_results, q_tick)


    def _record_deaths(self, tick: int) -> None:
        # The simulation goes on after a death, so the chart can show the overkill.
        for actor, character in self.actors.items():
            if character.current_hp <= 0 and actor not in self.deaths:
                self.deaths[actor] = tick
