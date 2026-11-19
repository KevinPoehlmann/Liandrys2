from collections import defaultdict
from dataclasses import replace
import math


from src.server.models.dataenums import (
    ActionType,
    Actor,
    Comparison,
    DamageType,
    DotState,
    EffectComp,
    EffectResult,
    EffectType,
    ProcessedDamageProperties,
    ProcessedHealProperties,
    ProcessedStatusProperties,
    QueueComponent,
    Target,
    TickEvent,
    Trigger,
    TICKRATE,
    to_ticks
)
from src.server.models.request import V1Response, Action
from src.server.models.rule import (
    ApplyBuffAction, Condition, DamageAction, DamageProps, HealAction, HealProps, RemoveBuffAction,
    ResetAttackAction, Rule, RuleAction, StatusAction, StatusProps
)
from src.server.simulation.character import Character
from src.server.simulation.buff_instance import BuffInstance
from src.server.simulation.events import BuffEnd, BuffTick, RuleEvent
from src.server.simulation.exceptions import SimulationError
from src.server.simulation.formula import FormulaContext, evaluate_formula

QueueEntry = QueueComponent | RuleEvent | BuffEnd | BuffTick




class Simulation():
    def __init__(self, blue: Character, red: Character, distance: int = 0):
        self.tick: int = 0
        self.distance: int = distance
        self.queue: dict[int, list[QueueEntry]] = defaultdict(list)
        self.dots: dict[tuple[ActionType, Actor], DotState] = {}
        self.effect_list: list[TickEvent] = []
        self.actors: dict[Actor, Character] = {
            Actor.BLUE: blue,
            Actor.RED: red
        }



    def do_combo(self, combo: list[Action]) -> V1Response:
        for i, action in enumerate(combo):
            self.do_action(action, i)
        self._process_remaining_queue()
        return V1Response(tick_rate=TICKRATE, damage=round(self.actors[Actor.RED].damage_taken), ticks=self.tick, effect_list=self.effect_list)


    def do_action(self, action: Action, index: int | None = None) -> None:
        self._wait_until_ready(action)
        try:
            self._cast(action)
        except Exception as e:
            raise SimulationError(
                message=str(e),
                action_index=index,
                action_type=action.action_type,
                actor=action.actor,
                phase="cast"
            ) from e


    def _wait_until_ready(self, action: Action) -> None:
        character = self.actors[action.actor]
        self._process_queue()
        ready = character.check_action_delay(action.action_type, self.tick)
        # Events before the action can still change when it is ready, e.g. the hit that consumes Tumble starts Q's cooldown.
        while self.queue and min(self.queue) <= ready:
            q_tick = min(self.queue)
            self.tick = max(self.tick, q_tick)
            self._process_tick(q_tick)
            ready = character.check_action_delay(action.action_type, self.tick)
        self.tick = ready


    def _cast(self, action: Action) -> None:
        start = self.tick
        character = self.actors[action.actor]
        action_effect = character.do_action(action, self.tick)
        self.tick = action_effect.tick
        self._queue_status(action_effect.effect_comps, action.actor)
        for rule_event in action_effect.rule_events:
            self._queue_rule(rule_event, self.tick)
        trigger = Trigger.ON_ATTACK if action.action_type == ActionType.AA else Trigger.ON_CAST
        self._fire(trigger, action.actor, action.target, action.action_type, self.tick)
        if action_effect.windup_cancel:
            # Everything else still waits for the windup; the cancelling slots may start right away.
            character.lock(action_effect.tick, action_effect.windup_cancel)
            self.tick = start


    def _fire(self, trigger: Trigger, actor: Actor, counterpart: Actor, source: ActionType, tick: int) -> None:
        # Rules are collected before any of them runs, so a buff created by this event can't react to it.
        for rule, slot, owner, buff in self.actors[actor].triggered_rules(trigger, source):
            bearer = actor if buff else None
            self._queue_rule(RuleEvent(rule=rule, slot=slot, owner=self._actor_of(owner), target=counterpart, bearer=bearer, buff=buff), tick)


    def _fire_hits(self, results: list[EffectResult], tick: int) -> None:
        for result in results:
            if result.source == ActionType.AA and result.type_ == EffectType.DAMAGE:
                self._fire(Trigger.ON_HIT, result.actor, result.target, ActionType.AA, tick)


    def _fire_stack(self, buff: str, buff_rules: list[Rule], slot: ActionType, owner: Actor, bearer: Actor, tick: int) -> None:
        # on_stack has no counterpart, so the bearer is also the `target`.
        for rule in buff_rules:
            if rule.trigger == Trigger.ON_STACK:
                self._queue_rule(RuleEvent(rule=rule, slot=slot, owner=owner, target=bearer, bearer=bearer, buff=buff), tick)


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


    def _actor_of(self, character: Character) -> Actor:
        return next(actor for actor, candidate in self.actors.items() if candidate is character)


    def _queue_rule(self, event: RuleEvent, tick: int) -> None:
        context = self._context(event, event.target)
        delay = to_ticks(evaluate_formula(event.rule.delay, context))
        speed = evaluate_formula(event.rule.speed, context)
        travel_time = to_ticks(self.distance / speed) if speed > 0 else 0
        self.queue.setdefault(tick + delay + travel_time, []).append(event)


    def _run_rule(self, event: RuleEvent, tick: int) -> list[QueueComponent]:
        if not all(self._holds(condition, event) for condition in event.rule.conditions):
            return []
        components = []
        for action in event.rule.actions:
            components.extend(self._run_action(action, event, tick))
        return components


    def _run_action(self, action: RuleAction, event: RuleEvent, tick: int) -> list[QueueComponent]:
        owner = self.actors[event.owner]
        match action:
            case DamageAction(props=props):
                return [self._damage(props, event)]
            case StatusAction(props=props):
                return [self._status(props, event)]
            case HealAction(props=props):
                return [self._heal(props, event)]
            case ApplyBuffAction(props=props):
                bearer = self._resolve_target(props.target, event)
                stacks = int(evaluate_formula(props.stacks, owner.formula_context(event.slot)))
                instance = self.actors[bearer].apply_buff(props.buff, owner, stacks, tick)
                if instance.end is not None:
                    self.queue.setdefault(instance.end, []).append(BuffEnd(bearer=bearer, buff=props.buff, end=instance.end))
                self._schedule_interval(bearer, instance)
                self._fire_stack(props.buff, instance.definition.rules, instance.slot, self._actor_of(instance.source), bearer, tick)
            case RemoveBuffAction(props=props):
                self.actors[self._resolve_target(props.target, event)].remove_buff(props.buff, tick)
            case ResetAttackAction():
                owner.reset_attack(tick)
            case _:
                raise NotImplementedError(f"Action '{action.type_}' is not supported yet")
        return []


    def _target_and_context(self, target: Target, event: RuleEvent) -> tuple[Actor, FormulaContext]:
        actor = self._resolve_target(target, event)
        return actor, self._context(event, actor)


    def _context(self, event: RuleEvent, target: Actor) -> FormulaContext:
        # Inside a buff rule, `stacks` are the stacks of that buff on its bearer.
        stacks = self.actors[event.bearer].get_buff_stacks(event.buff) if event.buff and event.bearer else 0
        return self.actors[event.owner].formula_context(event.slot, target=self.actors[target], stacks=stacks)


    def _schedule_interval(self, bearer: Actor, instance: BuffInstance) -> None:
        next_tick = self._next_interval(instance)
        # A refresh can move the next tick; the event at the old tick no longer matches and is ignored.
        if next_tick is not None and next_tick != instance.next_interval:
            instance.next_interval = next_tick
            self.queue.setdefault(next_tick, []).append(BuffTick(bearer=bearer, buff=instance.definition.name, tick=next_tick))


    @staticmethod
    def _next_interval(instance: BuffInstance) -> int | None:
        interval = evaluate_formula(instance.definition.interval, instance.source.formula_context(instance.slot))
        if interval <= 0:
            return None
        if instance.end is None:
            raise NotImplementedError(f"Buff '{instance.definition.name}' has an interval but no duration")
        # The rhythm is set by the first stack, refreshes keep it.
        definition, last = instance.definition, instance.last_interval
        k = 0 if definition.tick_on_apply else 1
        while last is not None and instance.start + to_ticks(k * interval) <= last:
            k += 1
        rhythm_tick = instance.start + to_ticks(k * interval)
        if rhythm_tick <= instance.end:
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
            RuleEvent(rule=rule, slot=instance.slot, owner=owner, target=buff_tick.bearer, bearer=buff_tick.bearer, buff=buff_tick.buff)
            for rule in instance.definition.rules if rule.trigger == Trigger.ON_INTERVAL
        ]


    def _damage(self, props: DamageProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        flat_pen, percent_pen = self.actors[event.owner].get_penetration(props.dmg_sub_type)
        processed = ProcessedDamageProperties(
            value=evaluate_formula(props.scaling, context),
            flat_pen=flat_pen,
            percent_pen=percent_pen,
            dmg_type=props.dmg_type[0] if props.dmg_type else DamageType.DEFAULT,
            dmg_sub_type=props.dmg_sub_type,
            vamp=props.vamp
        )
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.DAMAGE, props=processed)


    def _heal(self, props: HealProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        processed = ProcessedHealProperties(value=evaluate_formula(props.scaling, context))
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.HEAL, props=processed)


    def _status(self, props: StatusProps, event: RuleEvent) -> QueueComponent:
        target, context = self._target_and_context(props.target, event)
        processed = ProcessedStatusProperties(
            type_=props.status,
            duration=to_ticks(evaluate_formula(props.duration, context)),
            strength=evaluate_formula(props.strength, context)
        )
        return QueueComponent(source=event.slot, actor=event.owner, target=target, type_=EffectType.STATUS, props=processed)


    @staticmethod
    def _resolve_target(target: Target, event: RuleEvent) -> Actor:
        match target:
            case Target.SELF:
                return event.owner
            case Target.TARGET:
                return event.target
            case Target.BEARER if event.bearer is not None:
                return event.bearer
            case _:
                raise ValueError(f"Target '{target}' is only available inside buff rules")


    def _queue_status(self, effect_comps: list[EffectComp], actor: Actor) -> None:
        for effect_component in effect_comps:
            if effect_component.duration > 0:
                self._apply_dot(effect_component, actor)
            else:
                status_time = self.tick + self._calculate_delay(effect_component) + effect_component.duration
                self.queue.setdefault(status_time, []).append(QueueComponent(
                    source=effect_component.source,
                    actor=actor,
                    target=effect_component.target,
                    type_=effect_component.type_,
                    props=effect_component.props
                    ))


    def _process_queue(self) -> None:
        while self.queue and min(self.queue) <= self.tick:
            self._process_tick(min(self.queue))


    def _process_remaining_queue(self) -> None:
        while self.queue:
            q_tick = min(self.queue)
            self.tick = max(self.tick, q_tick)
            self._process_tick(q_tick)


    def _process_tick(self, q_tick: int) -> None:
        entries = self.queue.pop(q_tick)
        processed = []
        # Interval rules run before buff ends, so the tick at the end still sees the stacks.
        interval_events = [event for entry in entries if isinstance(entry, BuffTick) for event in self._interval_events(entry)]
        for event in [entry for entry in entries if isinstance(entry, RuleEvent)] + interval_events:
            processed.extend(self._run_rule(event, q_tick))
        raw = [entry for entry in entries if isinstance(entry, QueueComponent)]
        if raw or processed:
            self._apply_components(raw, processed, q_tick)
        for end in [entry for entry in entries if isinstance(entry, BuffEnd)]:
            self.actors[end.bearer].expire_buff(end.buff, end.end)


    def _apply_components(self, raw: list[QueueComponent], processed: list[QueueComponent], q_tick: int) -> None:
        evaluated_entries = processed
        evaluated_entries += self.actors[Actor.BLUE].evaluate([entry for entry in raw if entry.actor == Actor.BLUE])
        evaluated_entries += self.actors[Actor.RED].evaluate([entry for entry in raw if entry.actor == Actor.RED])

        effect_results = []
        while evaluated_entries:
            blue_list = [entry for entry in evaluated_entries if entry.target == Actor.BLUE]
            red_list = [entry for entry in evaluated_entries if entry.target == Actor.RED]

            evaluated_entries, results_blue = self.actors[Actor.BLUE].take_effects(blue_list, q_tick)
            evaluated_entries_red, results_red = self.actors[Actor.RED].take_effects(red_list, q_tick)
            evaluated_entries.extend(evaluated_entries_red)
            effect_results.extend(results_blue + results_red)

        self.effect_list.append(TickEvent(
            tick=q_tick,
            result=effect_results
        ))
        self._fire_hits(effect_results, q_tick)


    def _apply_dot(self, effect_comp: EffectComp, actor: Actor) -> None:
        if effect_comp.interval <= 0:
            #TODO: Log warning about invalid dot interval
            return

        interval_ticks = effect_comp.interval * TICKRATE
        existing_dot = self._find_existing_dot(effect_comp)
        i = math.floor((existing_dot.last_regular - existing_dot.start) / (interval_ticks)) + 1

        while existing_dot.start + math.ceil(i * interval_ticks - 1e-9) <= existing_dot.end:
            existing_dot.last_regular = existing_dot.start + math.ceil(i * interval_ticks - 1e-9)
            
            self.queue.setdefault(existing_dot.last_regular, []).append(QueueComponent(
                source=effect_comp.source,
                actor=actor,
                target=effect_comp.target,
                type_=effect_comp.type_,
                props=effect_comp.props
            ))
            i += 1
        if existing_dot.last_regular != existing_dot.end:
            self.queue.setdefault(existing_dot.end, []).append(QueueComponent(
                source=effect_comp.source,
                actor=actor,
                target=effect_comp.target,
                type_=effect_comp.type_,
                props=effect_comp.props
            ))


    def _find_existing_dot(self, effect_comp: EffectComp) -> DotState:
        existing_dot = self.dots.get((effect_comp.source, effect_comp.target))
        if existing_dot and existing_dot.end > self.tick:
            if existing_dot.end != existing_dot.last_regular:
                self._remove_dot_end(effect_comp.source, effect_comp.target, existing_dot.end)
            existing_dot.end = self.tick + self._calculate_delay(effect_comp) + effect_comp.duration
        else:
            existing_dot = DotState(
                start = self.tick + self._calculate_delay(effect_comp),
                last_regular = self.tick + self._calculate_delay(effect_comp),
                end = self.tick + self._calculate_delay(effect_comp) + effect_comp.duration
            )
            self.dots[(effect_comp.source, effect_comp.target)] = existing_dot
        return existing_dot


    def _remove_dot_end(self, source: ActionType, target: Actor, tick: int) -> None:
        if tick not in self.queue:
            return
        self.queue[tick] = [qc for qc in self.queue[tick] if not (qc.source == source and qc.target == target)]
        if not self.queue[tick]:
            del self.queue[tick]


    def _calculate_delay(self, effect_comp: EffectComp) -> int:
        travel_time = to_ticks(self.distance / effect_comp.speed) if effect_comp.speed > 0 else 0
        return effect_comp.delay + travel_time