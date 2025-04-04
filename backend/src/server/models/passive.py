from pydantic import BaseModel

from src.server.models.image import Image

from src.server.models.passive_effect import PassiveEffect


class Passive(BaseModel):
    name: str
    description: str = ""
    effects: list[PassiveEffect] = []
    ready_to_use: bool = False
    changes: list[str] = []


class ChampionPassive(Passive):
    image: Image


class ItemPassive(Passive):
    unique: bool