from collections import defaultdict


from src.server.models.dataenums import EffectComp, QueueComponent, EffectType, Actor
from src.server.models.request import V1Response, Action
from src.server.simulation.character import Character
from src.server.simulation.exceptions import SimulationError




class Simulation():
    def __init__(self, blue: Character, red: Character, distance: int = 0):
        self.timer: float = 0.0
        self.distance: int = distance
        self.queue: dict[float, list[QueueComponent]] = defaultdict(list)
        self.actors: dict[Actor, Character] = {
            Actor.BLUE: blue,
            Actor.RED: red
        }



    def do_combo(self, combo: list[Action]) -> V1Response:
        for i, action in enumerate(combo):
            delay = self.actors[action.actor].check_action_delay(action.action_type, self.timer)
            if delay:
                self.timer = delay
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
        return V1Response(damage=round(self.actors[Actor.RED].damage_taken), time=round(self.timer, 2))
    

    def _do_action(self, action: Action) -> None:
        action_effect = self.actors[action.actor].do_action(action, self.timer)
        self.timer = action_effect.time
        self._queue_status(action_effect.effect_comps, action.actor)
    

    def _queue_status(self, effect_comps: list[EffectComp], actor: Actor) -> None:
        for effect_component in effect_comps:
            if effect_component.duration > 0:
                self._apply_dot(effect_component, actor)
            status_time = self._calculate_delay(effect_component) + effect_component.duration
            self.queue.setdefault(status_time, []).append(QueueComponent(
                source=effect_component.source,
                actor=actor,
                target=effect_component.target,
                type_=effect_component.type_,
                props=effect_component.props
                ))


    def _process_queue(self) -> None:
        timestamps = sorted(self.queue.keys())
        for timestamp in timestamps:
            if timestamp > self.timer:
                break
            queue_entries = self.queue.pop(timestamp)

            evaluation_types = [EffectType.DAMAGE, EffectType.HEAL, EffectType.SHIELD]
            evaluation_entries = [entry for entry in queue_entries if entry.type_ in evaluation_types]
            evaluated_entries = [entry for entry in queue_entries if entry.type_ not in evaluation_types]
            evaluation_blue = [entry for entry in evaluation_entries if entry.actor == Actor.BLUE]
            evaluation_red = [entry for entry in evaluation_entries if entry.actor == Actor.RED]
            evaluated_entries.extend(self.actors[Actor.BLUE].evaluate(evaluation_blue))
            evaluated_entries.extend(self.actors[Actor.RED].evaluate(evaluation_red))

            while evaluated_entries:
                blue_list = [entry for entry in evaluated_entries if entry.target == Actor.BLUE]
                red_list = [entry for entry in evaluated_entries if entry.target == Actor.RED]

                evaluated_entries = self.actors[Actor.BLUE].take_effects(blue_list, timestamp)
                evaluated_entries.extend(self.actors[Actor.RED].take_effects(red_list, timestamp))
            


    def _apply_dot(self, effect_comp: EffectComp, actor: Actor) -> None:
        offset = self._calculate_offset(effect_comp, actor)
        while offset < effect_comp.duration + self._calculate_delay(effect_comp):
            self.queue.setdefault(offset, []).append(QueueComponent(
                source=effect_comp.source,
                actor=actor,
                target=effect_comp.target,
                type_=effect_comp.type_,
                props=effect_comp.props
                ))
            offset += effect_comp.interval
        if offset > effect_comp.duration + self._calculate_delay(effect_comp):
            self.queue.setdefault(offset, []).append(QueueComponent(
                source=effect_comp.source,
                actor=actor,
                target=effect_comp.target,
                type_=EffectType.SHADOW
            ))



    def _calculate_offset(self, effect_comp: EffectComp, actor: Actor) -> float:
        offset = self._calculate_delay(effect_comp) + effect_comp.interval
        existing_dots: list[tuple[float, QueueComponent]] = [dot for dot in self.queue.items() for d in dot[1] if d.source == effect_comp.source and d.actor == actor]
        if existing_dots:
            existing_dots.sort(reverse=True)
            last_dot = next((d for d in existing_dots[0][1] if d.source == effect_comp.source and d.actor == actor), None)
            if last_dot.type_ != EffectType.SHADOW:
                offset = max(offset, existing_dots[0][0] + effect_comp.interval)
            else:
                if len(existing_dots) > 1 and offset - effect_comp.interval < existing_dots[1][0]:
                    offset = existing_dots[0][0]
                self._remove_last_dots(effect_comp, existing_dots, last_dot)
        return offset


    def _remove_last_dots(self, effect_comp: EffectComp, existing_dots: list[tuple[float, list[QueueComponent]]], last_dot: QueueComponent) -> None:
        self.queue[existing_dots[0][0]].remove(last_dot)
        if len(self.queue[existing_dots[0][0]]) == 0:
            self.queue.pop(existing_dots[0][0])
        if len(existing_dots) > 1 and existing_dots[0][0] - existing_dots[1][0] < effect_comp.interval:
            if existing_dots[1][0] < self._calculate_delay(effect_comp):
                return
            if existing_dots[0][0] - existing_dots[1][0] < effect_comp.interval:
                # removing the last, irregularly ticking dot
                self.queue[existing_dots[1][0]] = [d for d in existing_dots[1][1] if d.source != effect_comp.source or d.actor != last_dot.actor]
                if len(self.queue[existing_dots[1][0]]) == 0:
                    self.queue.pop(existing_dots[1][0])


    def _calculate_delay(self, effect_comp: EffectComp) -> float:
        travel_time = (self.distance / effect_comp.speed) if effect_comp.speed > 0 else 0
        return self.timer + effect_comp.delay + travel_time