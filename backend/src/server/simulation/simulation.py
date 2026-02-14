from collections import defaultdict
import math


from src.server.models.dataenums import DotState, EffectComp, QueueComponent, EffectType, Actor, ActionType, TickEvent, TICKRATE
from src.server.models.request import V1Response, Action
from src.server.simulation.character import Character
from src.server.simulation.exceptions import SimulationError




class Simulation():
    def __init__(self, blue: Character, red: Character, distance: int = 0):
        self.tick: int = 0
        self.distance: int = distance
        self.queue: dict[int, list[QueueComponent]] = defaultdict(list)
        self.dots: dict[tuple[ActionType, Actor], DotState] = {}
        self.effect_list: list[TickEvent] = []
        self.actors: dict[Actor, Character] = {
            Actor.BLUE: blue,
            Actor.RED: red
        }



    def do_combo(self, combo: list[Action]) -> V1Response:
        for i, action in enumerate(combo):
            delay = self.actors[action.actor].check_action_delay(action.action_type, self.tick)
            if delay:
                self.tick = delay
            self._process_queue()
            try:
                self._do_action(action)
            except Exception as e:
                raise SimulationError(
                    message=str(e),
                    action_index=i,
                    action_type=action.action_type,
                    actor=action.actor,
                    phase="cast"
                ) from e
        self._process_queue()
        return V1Response(tick_rate=TICKRATE, damage=round(self.actors[Actor.RED].damage_taken), ticks=self.tick, effect_list=self.effect_list)
    

    def _do_action(self, action: Action) -> None:
        action_effect = self.actors[action.actor].do_action(action, self.tick)
        self.tick = action_effect.tick
        self._queue_status(action_effect.effect_comps, action.actor)
    

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
        q_ticks = sorted(self.queue.keys())
        for q_tick in q_ticks:
            if q_tick > self.tick:
                break
            queue_entries = self.queue.pop(q_tick)

            evaluation_types = [EffectType.DAMAGE, EffectType.HEAL, EffectType.SHIELD]
            evaluation_entries = [entry for entry in queue_entries if entry.type_ in evaluation_types]
            evaluated_entries = [entry for entry in queue_entries if entry.type_ not in evaluation_types]
            evaluation_blue = [entry for entry in evaluation_entries if entry.actor == Actor.BLUE]
            evaluation_red = [entry for entry in evaluation_entries if entry.actor == Actor.RED]
            evaluated_entries.extend(self.actors[Actor.BLUE].evaluate(evaluation_blue))
            evaluated_entries.extend(self.actors[Actor.RED].evaluate(evaluation_red))

            effect_results = []
            while evaluated_entries:
                blue_list = [entry for entry in evaluated_entries if entry.target == Actor.BLUE]
                red_list = [entry for entry in evaluated_entries if entry.target == Actor.RED]

                evaluated_entries, effect_results = self.actors[Actor.BLUE].take_effects(blue_list, q_tick)
                evaluated_entries_b, effect_results_b = self.actors[Actor.RED].take_effects(red_list, q_tick)
                evaluated_entries.extend(evaluated_entries_b)
                effect_results.extend(effect_results_b)
                
            self.effect_list.append(TickEvent(
                tick=q_tick,
                result=effect_results
            ))
            

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
        travel_time = (math.ceil(self.distance / effect_comp.speed * TICKRATE - 1e-9)) if effect_comp.speed > 0 else 0
        return effect_comp.delay + travel_time