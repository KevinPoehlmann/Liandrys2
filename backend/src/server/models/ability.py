from pydantic import BaseModel

from src.server.models.change import Change
from src.server.models.image import Image
from src.server.models.pet import Pet
from src.server.models.rule import Buff, Input, Rule, Stage, StatModifier

from src.server.models.enums import ActionType, ActiveType, CostResource




class Ability(BaseModel):
    name: str
    description: str = ""
    cost: str = "0"
    cost_resource: CostResource = CostResource.NONE  # paid when the cast starts
    cooldown: str = "0"
    cast_time: str = "0"
    recharge: str = "0"
    charges: str = "0"  # 0: no charges, `recharge` is the time per charge
    cooldown_starts_after: str | None = None
    cooldown_starts_on_cast: bool = False
    usable_during_cc: bool = False  # Cleanse: only suppression and stasis block it
    counts_as_cast: bool = True  # False: no on-cast effects (Nidalee's form swap doesn't grant Spellblade)
    stages: list[Stage] = []
    rules: list[Rule] = []
    stats: list[StatModifier] = []
    buffs: list[Buff] = []
    inputs: list[Input] = []
    pets: list[Pet] = []
    assumptions: list[str] = []  # what we assumed where data was missing, shown to the user
    values: dict[str, str] = {}  # loader-owned named values (BaseDamage, TotalDamage, ...), overwritten every patch
    tooltip: str = ""  # loader-owned, Riot's text with @Name@ placeholders for the values
    raw_stats: dict[str, str] = {}
    changes: list[Change] = []
    validated: bool = False




class ChampionAbility(Ability):
    maxrank: int
    image: Image


class ExtraAbility(ChampionAbility):
    """An ability a buff puts on Q/W/E/R (Nidalee's cougar form, later Hwei's subcasts)."""
    key: str  # what Buff.replaces points to, e.g. "takedown"
    rank_from: ActionType  # whose ability points it uses (Nidalee's cougar abilities: R)


class ItemActive(Ability):
    type_: ActiveType
    unique: bool = False



class ShortChampionAbility(BaseModel):
    name: str
    maxrank: int
    image: Image
    validated: bool