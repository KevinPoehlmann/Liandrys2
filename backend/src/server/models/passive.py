from src.server.models.change import Change
from src.server.models.image import Image
from src.server.models.rule import Buff, Input, Rule, StatModifier, StrictModel


class Passive(StrictModel):
    name: str
    rules: list[Rule] = []
    stats: list[StatModifier] = []
    buffs: list[Buff] = []
    inputs: list[Input] = []
    assumptions: list[str] = []  # what we assumed where data was missing, shown to the user
    values: dict[str, str] = {}  # loader-owned named values (BaseDamage, TotalDamage, ...), overwritten every patch
    tooltip: str = ""  # loader-owned, Riot's text with @Name@ placeholders for the values
    raw_stats: dict[str, str] = {}
    changes: list[Change] = []
    validated: bool = False



class ChampionPassive(Passive):
    image: Image


class ItemPassive(Passive):
    unique: bool = False