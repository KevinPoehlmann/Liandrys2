from src.server.models.enums import Actor, CostResource, EffectType
from src.server.simulation.simulation import Simulation


def regenerated_health(sim: Simulation, actor: Actor, until: int | None = None) -> float:
    """Health regeneration is tested in test_resources.py; other tests take it out of their health expectations."""
    return sum(
        result.value
        for event in sim.effect_list if until is None or event.tick <= until
        for result in event.result
        if result.type_ == EffectType.REGEN and result.resource == CostResource.HEALTH and result.target == actor
    )
