from pydantic import BaseModel

from src.server.models.image import Image
from src.server.models.pet import Pet
from src.server.models.rule import Buff, Input, Rule, Stage, StatModifier

from src.server.models.dataenums import (
    ActiveType,
    CostResource
)




class Ability(BaseModel):
    name: str
    description: str = ""
    cost: str = "0"
    cost_resource: CostResource = CostResource.NONE  # paid when the cast starts
    cooldown: str = "0"
    cast_time: str = "0"
    recharge: str = "0"
    cooldown_starts_after: str | None = None
    cooldown_starts_on_cast: bool = False
    usable_during_cc: bool = False  # Cleanse: only suppression and stasis block it
    stages: list[Stage] = []
    rules: list[Rule] = []
    stats: list[StatModifier] = []
    buffs: list[Buff] = []
    inputs: list[Input] = []
    pets: list[Pet] = []
    assumptions: list[str] = []  # what we assumed where data was missing, shown to the user
    raw_stats: dict[str, str] = {}
    changes: list[str] = []
    validated: bool = False




class ChampionAbility(Ability):
    maxrank: int
    image: Image


class ItemActive(Ability):
    type_: ActiveType
    unique: bool = False



class ShortChampionAbility(BaseModel):
    name: str
    maxrank: int
    image: Image
    validated: bool