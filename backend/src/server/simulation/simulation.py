from collections import defaultdict


from src.server.models.dataenums import ActionType, EffectComp, QueueComponent, EffectType, Target
from src.server.models.request import V1Response
from src.server.simulation.character import Character




class Simulation():
    def __init__(self, attacker: Character, defender: Character, distance: int = 0):
        self.timer: float = 0.0
        self.attacker: Character = attacker
        self.defender: Character = defender
        self.distance: int = distance
        self.queue: dict[float, QueueComponent] = defaultdict(list)



    def do_combo(self, combo: list[ActionType]) -> V1Response:
        for action in combo:
            delay = self.attacker.check_action_delay(action, self.timer)
            if delay:
                self.timer = delay
                self.process_queue()
            self.do_action(action)
        self.process_queue()
        return V1Response(damage=round(self.defender.damage_taken), time=round(self.timer, 2))
    

    def do_action(self, key: ActionType) -> None:
        action_effect = self.attacker.do_action(key, self.timer)
        self.timer = action_effect.time
        self.queue_status(action_effect.effect_comps)
        self.process_queue()
    

    def queue_status(self, effect_comps: list[EffectComp]) -> None:
        for effect_component in effect_comps:
            if effect_component.duration > 0:
                self.apply_dot(effect_component)
            status_time = self.calculate_delay(effect_component) + effect_component.duration
            self.queue.setdefault(status_time, []).append(QueueComponent(
                source=effect_component.source,
                type_=effect_component.type_,
                target=effect_component.target,
                props=effect_component.props
                ))


    def process_queue(self) -> None:
        timestamps = sorted(self.queue.keys())
        for timestamp in timestamps:
            if timestamp > self.timer:
                break
            queue_entries = self.queue.pop(timestamp)

            evaluation_types = [EffectType.DAMAGE, EffectType.HEAL, EffectType.SHIELD]
            evaluation_entries = [entry for entry in queue_entries if entry.type_ in evaluation_types]
            other_entries = [entry for entry in queue_entries if entry.type_ not in evaluation_types]
            evaluated_entries = self.attacker.evaluate(evaluation_entries)
            other_entries.extend(evaluated_entries)

            defender_list = [entry for entry in other_entries if entry.target == Target.DEFENDER]
            attacker_list = [entry for entry in other_entries if entry.target == Target.ATTACKER]

            self.defender.take_effects(defender_list, timestamp)
            self.attacker.take_effects(attacker_list, timestamp)


    def apply_dot(self, effect_comp: EffectComp) -> None:
        offset = self.calculate_offset(effect_comp)
        while offset < effect_comp.duration + self.calculate_delay(effect_comp):
            self.queue.setdefault(offset, []).append(QueueComponent(
                effect_comp.source,
                type_=effect_comp.type_,
                target=effect_comp.target,
                props=effect_comp.props
                ))
            offset += effect_comp.interval
        if offset > effect_comp.duration + self.calculate_delay(effect_comp):
            self.queue.setdefault(offset, []).append(QueueComponent(
                source=effect_comp.source,
                type_=EffectType.SHADOW,
                target=effect_comp.target
            ))



    def calculate_offset(self, effect_comp: EffectComp) -> float:
        offset = self.calculate_delay(effect_comp) + effect_comp.interval
        existing_dots: list[tuple[float, QueueComponent]] = [dot for dot in self.queue.items() for d in dot[1] if d.source == effect_comp.source]
        if existing_dots:
            existing_dots.sort(reverse=True)
            last_dot = next((d for d in existing_dots[0][1] if d.source == effect_comp.source), None)
            if last_dot.type_ != EffectType.SHADOW:
                offset = max(offset, existing_dots[0][0] + effect_comp.interval)
            else:
                if len(existing_dots) > 1 and offset - effect_comp.interval < existing_dots[1][0]:
                    offset = existing_dots[0][0]
                self.remove_last_dots(effect_comp, existing_dots, last_dot)
        return offset


    def remove_last_dots(self, effect_comp: EffectComp, existing_dots: list[tuple[float, list[QueueComponent]]], last_dot: QueueComponent) -> None:
        self.queue[existing_dots[0][0]].remove(last_dot)
        if len(self.queue[existing_dots[0][0]]) == 0:
            self.queue.pop(existing_dots[0][0])
        if len(existing_dots) > 1 and existing_dots[0][0] - existing_dots[1][0] < effect_comp.interval:
            if existing_dots[1][0] < self.calculate_delay(effect_comp):
                return
            if existing_dots[0][0] - existing_dots[1][0] < effect_comp.interval:
                # removing the last, irregularly ticking dot
                self.queue[existing_dots[1][0]] = [d for d in existing_dots[1][1] if d.source != effect_comp.source]
                if len(self.queue[existing_dots[1][0]]) == 0:
                    self.queue.pop(existing_dots[1][0])


    def calculate_delay(self, effect_comp: EffectComp) -> float:
        travel_time = (self.distance / effect_comp.speed) if effect_comp.speed > 0 else 0
        return self.timer + effect_comp.delay + travel_time