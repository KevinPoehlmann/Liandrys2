from collections import defaultdict


from src.server.models.dataenums import ActionType, EffectDamage, QueueDamage
from src.server.models.request import V1Response, DummyResponse
from src.server.simulation.unit import Dummy, Character


class DummySimulation():
    def __init__(self, dummy: Dummy, character: Character, distance: int = 0):
        self.timer: float = 0.0
        self.dummy: Dummy = dummy
        self.character: Character = character
        self.distance: int = distance
        self.damage_queue: dict[float, QueueDamage] = defaultdict(list)



    def do_combo(self, combo: list[ActionType]) -> DummyResponse:
        for action in combo:
            self.do_action(action)
        self.process_damage_queue()
        return DummyResponse(damage=round(self.dummy.damage_taken), time=round(self.timer, 2))


    def do_action(self, key: ActionType) -> None:
        action_effect = self.character.do_action(key, self.timer)
        self.timer = action_effect.time
        self.queue_damage(action_effect.damages)
        self.process_damage_queue()


    def queue_damage(self, effect_damages: list[EffectDamage]) -> None:
        for effect_damage in effect_damages:
            if effect_damage.duration > 0:
                self.apply_dot(effect_damage)
            damage_time = self.calculate_damage_delay(effect_damage) + effect_damage.duration
            self.damage_queue.setdefault(damage_time, []).append(QueueDamage(
                effect_damage.source,
                effect_damage.scaling,
                effect_damage.dmg_type,
                effect_damage.dmg_sub_type,
                effect_damage.dmg_calc))


    def process_damage_queue(self) -> None:
        timestamps = sorted(self.damage_queue.keys())
        for timestamp in timestamps:
            if timestamp > self.timer:
                break
            damage_list = self.character.evaluate_scaling(self.damage_queue[timestamp])
            self.damage_queue.pop(timestamp)
            self.dummy.take_damge(damage_list)


    def apply_dot(self, effect_damage: EffectDamage) -> None:
        offset = self.calculate_offset(effect_damage)
        while offset < effect_damage.duration + self.calculate_damage_delay(effect_damage):
            self.damage_queue.setdefault(offset, []).append(QueueDamage(
                effect_damage.source,
                effect_damage.scaling,
                effect_damage.dmg_type,
                effect_damage.dmg_sub_type,
                effect_damage.dmg_calc))
            offset += effect_damage.interval
        if offset > effect_damage.duration + self.timer:
            self.damage_queue.setdefault(offset, []).append(QueueDamage(effect_damage.source, "shadow", None))



    def calculate_offset(self, effect_damage: EffectDamage) -> float:
        offset = self.calculate_damage_delay(effect_damage) + effect_damage.interval
        existing_dots = [dot for dot in self.damage_queue.items() for d in dot[1] if d.source == effect_damage.source]
        if existing_dots:
            existing_dots.sort(reverse=True)
            last_dot = next((d for d in existing_dots[0][1] if d.source == effect_damage.source), None)
            if last_dot.scaling != "shadow":
                offset = max(offset, existing_dots[0][0] + effect_damage.interval)
            else:
                if len(existing_dots) > 1 and offset - effect_damage.interval < existing_dots[1][0]:
                    offset = existing_dots[0][0]
                self.remove_last_dots(effect_damage, existing_dots, last_dot)
        return offset


    def remove_last_dots(self, effect_damage: EffectDamage, existing_dots: list[tuple[float, list[QueueDamage]]], last_dot: QueueDamage) -> None:
        self.damage_queue[existing_dots[0][0]].remove(last_dot)
        if len(self.damage_queue[existing_dots[0][0]]) == 0:
            self.damage_queue.pop(existing_dots[0][0])
        if len(existing_dots) > 1:
            if existing_dots[1][0] < self.calculate_damage_delay(effect_damage):
                return
            if existing_dots[0][0] - existing_dots[1][0] < effect_damage.interval:
                # removing the last, irregularly ticking dot
                self.damage_queue[existing_dots[1][0]] = [d for d in existing_dots[1][1] if d.source != effect_damage.source]
                if len(self.damage_queue[existing_dots[1][0]]) == 0:
                    self.damage_queue.pop(existing_dots[1][0])
    

    def calculate_damage_delay(self, effect_damage: EffectDamage) -> float:
        travel_time = (self.distance / effect_damage.speed) if effect_damage.speed > 0 else 0
        return self.timer + effect_damage.delay + travel_time



class V1Simulation():
    def __init__(self, attacker: Character, defender: Character):
        self.timer: float = 0.0
        self.attacker: Character = attacker
        self.defender: Character = defender
        self.damage_queue: dict[float, QueueDamage] = defaultdict(list)



    def do_combo(self, combo: list[ActionType]) -> V1Response:
        for action in combo:
            self.do_action(action)
        self.process_damage_queue()
        return V1Response(damage=round(self.defender.damage_taken), time=round(self.timer, 2))
    

    def do_action(self, key: ActionType) -> None:
        action_effect = self.attacker.do_action(key, self.timer)
        self.timer = action_effect.time
        self.queue_damage(action_effect.damages)
        self.process_damage_queue()
    

    def queue_damage(self, effect_damages: list[EffectDamage]) -> None:
        for effect_damage in effect_damages:
            if effect_damage.duration > 0:
                self.apply_dot(effect_damage)
            self.damage_queue.setdefault(self.timer + effect_damage.duration, []).append(QueueDamage(
                effect_damage.source,
                effect_damage.scaling,
                effect_damage.dmg_type,
                effect_damage.dmg_sub_type,
                effect_damage.dmg_calc))


    def process_damage_queue(self) -> None:
        timestamps = sorted(self.damage_queue.keys())
        for timestamp in timestamps:
            if timestamp > self.timer:
                break
            damage_list = self.attacker.evaluate_scaling(self.damage_queue[timestamp])
            self.damage_queue.pop(timestamp)
            self.defender.take_damge(damage_list)


    def apply_dot(self, effect_damage: EffectDamage) -> None:
        offset = self.calculate_offset(effect_damage)
        while offset < effect_damage.duration + self.timer:
            self.damage_queue.setdefault(offset, []).append(QueueDamage(
                effect_damage.source,
                effect_damage.scaling,
                effect_damage.dmg_type,
                effect_damage.dmg_sub_type,
                effect_damage.dmg_calc))
            offset += effect_damage.interval
        if offset > effect_damage.duration + self.timer:
            self.damage_queue.setdefault(offset, []).append(QueueDamage(effect_damage.source, "shadow", None))



    def calculate_offset(self, effect_damage: EffectDamage) -> float:
        offset = self.timer + effect_damage.interval
        existing_dots = [dot for dot in self.damage_queue.items() for d in dot[1] if d.source == effect_damage.source]
        if existing_dots:
            existing_dots.sort(reverse=True)
            last_dot = next((d for d in existing_dots[0][1] if d.source == effect_damage.source), None)
            if last_dot.scaling != "shadow":
                offset = existing_dots[0][0] + effect_damage.interval
            else:
                if len(existing_dots) == 1:
                    offset = effect_damage.interval
                else:
                    offset = existing_dots[0][0]
                self.remove_last_dots(effect_damage, existing_dots, last_dot)
        return offset


    def remove_last_dots(self, effect_damage: EffectDamage, existing_dots: list[tuple[float, list[QueueDamage]]], last_dot: QueueDamage) -> None:
        self.damage_queue[existing_dots[0][0]].remove(last_dot)
        if len(self.damage_queue[existing_dots[0][0]]) == 0:
            self.damage_queue.pop(existing_dots[0][0])
        if len(existing_dots) > 1:
            if existing_dots[0][0] - existing_dots[1][0] < effect_damage.interval:
                # removing the last, irregularly ticking dot
                self.damage_queue[existing_dots[1][0]] = [d for d in existing_dots[1][1] if d.source != effect_damage.source]
                if len(self.damage_queue[existing_dots[1][0]]) == 0:
                    self.damage_queue.pop(existing_dots[1][0])