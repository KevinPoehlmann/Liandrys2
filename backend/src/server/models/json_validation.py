from pathlib import Path
from pydantic import BaseModel, Field, validator, ValidationError



class ImageJson(BaseModel):
    full: str
    sprite: str
    group: str
    x: int
    y: int
    w: int
    h: int



class ChampionsJson(BaseModel):
    typ: str = Field(..., alias="type")
    frmt: str = Field(..., alias="format")
    version: str
    data: dict


class StatsJson(BaseModel):
    hp: float
    hpperlevel: int
    mp: float
    mpperlevel: float
    movespeed: int
    armor: int
    armorperlevel: float
    spellblock: float
    spellblockperlevel: float
    attackrange: int
    hpregen: float
    hpregenperlevel: float
    mpregen: float
    mpregenperlevel: float
    crit: int
    critperlevel: int
    attackdamage: float
    attackdamageperlevel: float
    attackspeedperlevel: float
    attackspeed: float


class SpellJson(BaseModel):
    id_: str = Field(..., alias="id")
    name: str
    description: str
    tooltip: str
    leveltip: dict
    maxrank: int
    cooldown: list[float]
    cooldownBurn: str
    cost: list[int]
    costBurn: str
    datavalues: dict
    effect: list
    effectBurn: list
    vars: list
    costType: str
    maxammo: str
    range_: list[int] = Field(..., alias="range")
    rangeBurn: str
    image: ImageJson
    resource: str


class PassiveJson(BaseModel):
    name: str
    description: str
    image: ImageJson


class ChampionJson(BaseModel):
    id_: str = Field(..., alias="id")
    key: str
    name: str
    title: str
    image: ImageJson
    skins: list[dict]
    lore: str
    blurb: str
    allytps: list[str]
    enemytips: list[str]
    tags: list[str]
    partype: str
    info: dict
    stats: StatsJson
    spells: list[SpellJson]
    passive: PassiveJson
    recommended: list




class ItemsJson(BaseModel):
    typ: str = Field(..., alias="type")
    version: str
    basic: dict
    data: dict
    groups: list[dict]
    tree: list[dict]


class GoldJson(BaseModel):
    base: int
    purchasable: bool
    total: int
    sell: int


class ItemJson(BaseModel):
    name: str
    description: str
    colloq: str
    plaintext: str
    from_: list[str] | None = Field(alias="from")
    into: list[str] | None = None
    image: ImageJson
    gold: GoldJson
    tags: list[str]
    maps: dict
    stats: dict



class RuneJson(BaseModel):
    id_: int = Field(..., alias="id")
    key: str
    icon: str
    name: str
    shortDesc: str
    longDesc: str


class RuneRowJson(BaseModel):
    runes: list[RuneJson]


class RuneTreeJson(BaseModel):
    id_: int = Field(..., alias="id")
    key: str
    name: str
    slots: list[RuneRowJson]



class SummonerspellsJson(BaseModel):
    typ: str = Field(..., alias="type")
    version: str
    data: dict


class SummonerspellJson(BaseModel):
    id_: str = Field(..., alias="id")
    name: str
    description: str
    tooltip: str
    maxrank: int
    cooldown: list[int]
    cooldownBurn: str
    cost: list[int]
    costBurn: str
    datavalues: dict
    effect: list
    effectBurn: list
    vars: list
    key: str
    summonerLevel: int
    modes: list[str]
    costType: str
    maxammo: str
    range_: list[int] = Field(..., alias="range")
    rangeBurn: str
    image: ImageJson
    resource: str




#--------------------------------------------------------------------------

#TODO convert from str to Path
class PathJson(BaseModel):
    championImage: Path
    itemImage: Path
    passiveImage: Path
    runeImage: Path
    spellImage: Path
    sprite: Path
    summonerspellImage: Path

    @validator("championImage", "itemImage", "passiveImage", "runeImage", "spellImage", "sprite", "summonerspellImage", pre=True, allow_reuse=True)
    def convert_to_path(cls, value):
        return Path(value)


class UrlJson(BaseModel):
    patches: str
    dataLink: str
    wiki: str
    championList: str
    championData: str
    championWiki: str
    championImage: str
    itemList: str
    itemImage: str
    passiveImage: str
    runeList: str
    runeImage: str
    spellImage: str
    sprite: str
    summonerspellList: str
    summonerspellImage: str


class InfoJson(BaseModel):
    paths: PathJson
    urls: UrlJson
    itemStatDict: dict
    itemWikiNames: dict