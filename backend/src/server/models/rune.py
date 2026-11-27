from datetime import datetime

from pydantic import BaseModel, Field

from src.server.models.change import Change
from src.server.models.champion import WikiTemplate
from src.server.models.passive import Passive
from src.server.models.image import Image
from src.server.models.pydanticid import PydanticObjectId


class NewRune(BaseModel):
    rune_id: int
    name: str
    patch: str
    tree: str
    tree_id: int
    row: int
    slot: int
    passive: Passive
    validated: bool = False
    changes: list[Change] = []
    image: Image | None = None

    

class Rune(NewRune):
    id: PydanticObjectId = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


class ShortRune(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    rune_id: int
    name: str
    tree: str
    tree_id: int
    row: int
    slot: int
    validated: bool
    image: Image


class RawRune(BaseModel):
    """Everything the loader downloaded for one rune and patch, unchanged. Never read by the user API.
    A stat shard in two rows (Adaptive Force) has one raw document."""
    rune_id: int
    patch: str
    build: str
    fetched_at: datetime
    cdragon: dict  # the perk's record in perks.cdtb.bin.json; untyped on purpose like RawChampion.cdragon
    strings: dict[str, str] = {}  # its entries from lol.stringtable.json (name, tooltip, descriptions)
    wiki_data: WikiTemplate | None = None  # Template:Rune data <name>: the wiki's description and cooldown
    wiki: WikiTemplate | None = None  # the wiki article's wikitext, for its notes

