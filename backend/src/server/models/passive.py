from pydantic import BaseModel

from src.server.models.image import Image

from src.server.models.passive_effect import PassiveEffect


class Passive(BaseModel):
    name: str
    description: str = ""
    static_cooldown: str = ""
    effects: list[PassiveEffect] = []
    raw_stats: dict[str, str] = {}
    changes: list[str] = []
    validated: bool = False


class ChampionPassive(Passive):
    image: Image


class ItemPassive(Passive):
    unique: bool = False