import re

from pydantic import Field, validator

from src.server.models.dataenums import DamageSubType, DamageType, Stat
from src.server.models.passive import Passive
from src.server.models.rule import StrictModel


# The name becomes part of the actor id, e.g. 'blue.tibbers'.
PET_NAME = re.compile(r"[a-z][a-z0-9_]*")


class PetAttack(StrictModel):
    scaling: str
    dmg_type: list[DamageType] = [DamageType.BASIC]
    dmg_sub_type: DamageSubType = DamageSubType.PHYSIC
    windup: float = Field(..., gt=0, lt=1)  # share of the attack time, like a champion's attack_windup
    missile_speed: int = 0


class Pet(StrictModel):
    """A unit summoned by an ability. It attacks its owner's enemy on its own until it expires.

    Stat formulas use the rank of the summoning ability and read the owner with `owner_`, e.g. `owner_ap`.
    """
    name: str
    duration: str
    stats: dict[Stat, str] = {}
    attack: PetAttack
    passive: Passive = Passive(name="")

    @validator("name")
    def name_fits_actor_id(cls, name: str) -> str:
        if not PET_NAME.fullmatch(name):
            raise ValueError(f"Pet name '{name}' must be lowercase letters, digits and '_', e.g. 'tibbers'")
        return name
