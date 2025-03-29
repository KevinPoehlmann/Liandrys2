from collections import defaultdict


from src.server.models.dataenums import ActionType, EffectStatus, QueueStatus, StatusType, Target
from src.server.models.request import V1Response
from src.server.simulation.unit import Character




class Simulation():
    def __init__(self, attacker: Character, defender: Character, distance: int = 0):
        self.timer: float = 0.0
        self.attacker: Character = attacker
        self.defender: Character = defender
        self.distance: int = distance
        self.queue: dict[float, QueueStatus] = defaultdict(list)



    def do_combo(self, combo: list[ActionType]) -> V1Response:
        for action in combo:
            self.do_action(action)
        self.process_queue()
        return V1Response(damage=round(self.defender.damage_taken), time=round(self.timer, 2))
    

    def do_action(self, key: ActionType) -> None:
        action_effect = self.attacker.do_action(key, self.timer)
        self.timer = action_effect.time
        self.queue_status(action_effect.stati)
        self.process_queue()
    

    def queue_status(self, effect_stati: list[EffectStatus]) -> None:
        for effect_status in effect_stati:
            if effect_status.duration > 0:
                self.apply_dot(effect_status)
            status_time = self.calculate_delay(effect_status) + effect_status.duration
            self.queue.setdefault(status_time, []).append(QueueStatus(
                source=effect_status.source,
                type_=effect_status.type_,
                target=effect_status.target,
                props=effect_status.props
                ))


    def process_queue(self) -> None:
        timestamps = sorted(self.queue.keys())
        for timestamp in timestamps:
            if timestamp > self.timer:
                break
            queue_entries = self.queue.pop(timestamp)

            evaluation_types = [StatusType.DAMAGE, StatusType.HEAL, StatusType.SHIELD]
            evaluation_entries = [entry for entry in queue_entries if entry.type_ in evaluation_types]
            other_entries = [entry for entry in queue_entries if entry.type_ not in evaluation_types]
            evaluated_entries = self.attacker.evaluate(evaluation_entries)
            other_entries.extend(evaluated_entries)

            defender_list = [entry for entry in other_entries if entry.target == Target.DEFENDER]
            attacker_list = [entry for entry in other_entries if entry.target == Target.ATTACKER]

            self.defender.take_stati(defender_list, timestamp)
            self.attacker.take_stati(attacker_list, timestamp)


    def apply_dot(self, effect_status: EffectStatus) -> None:
        offset = self.calculate_offset(effect_status)
        while offset < effect_status.duration + self.calculate_delay(effect_status):
            self.queue.setdefault(offset, []).append(QueueStatus(
                effect_status.source,
                type_=effect_status.type_,
                target=effect_status.target,
                props=effect_status.props
                ))
            offset += effect_status.interval
        if offset > effect_status.duration + self.calculate_delay(effect_status):
            self.queue.setdefault(offset, []).append(QueueStatus(
                source=effect_status.source,
                type_=StatusType.SHADOW,
                target=effect_status.target
            ))



    def calculate_offset(self, effect_status: EffectStatus) -> float:
        offset = self.calculate_delay(effect_status) + effect_status.interval
        existing_dots: list[tuple[float, QueueStatus]] = [dot for dot in self.queue.items() for d in dot[1] if d.source == effect_status.source]
        if existing_dots:
            existing_dots.sort(reverse=True)
            last_dot = next((d for d in existing_dots[0][1] if d.source == effect_status.source), None)
            if last_dot.type_ != StatusType.SHADOW:
                offset = max(offset, existing_dots[0][0] + effect_status.interval)
            else:
                if len(existing_dots) > 1 and offset - effect_status.interval < existing_dots[1][0]:
                    offset = existing_dots[0][0]
                self.remove_last_dots(effect_status, existing_dots, last_dot)
        return offset


    def remove_last_dots(self, effect_status: EffectStatus, existing_dots: list[tuple[float, list[QueueStatus]]], last_dot: QueueStatus) -> None:
        self.queue[existing_dots[0][0]].remove(last_dot)
        if len(self.queue[existing_dots[0][0]]) == 0:
            self.queue.pop(existing_dots[0][0])
        if len(existing_dots) > 1 and existing_dots[0][0] - existing_dots[1][0] < effect_status.interval:
            if existing_dots[1][0] < self.calculate_delay(effect_status):
                return
            if existing_dots[0][0] - existing_dots[1][0] < effect_status.interval:
                # removing the last, irregularly ticking dot
                self.queue[existing_dots[1][0]] = [d for d in existing_dots[1][1] if d.source != effect_status.source]
                if len(self.queue[existing_dots[1][0]]) == 0:
                    self.queue.pop(existing_dots[1][0])


    def calculate_delay(self, effect_status: EffectStatus) -> float:
        travel_time = (self.distance / effect_status.speed) if effect_status.speed > 0 else 0
        return self.timer + effect_status.delay + travel_time