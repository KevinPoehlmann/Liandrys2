import json
import requests
import re





class Champion(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    key: str
    name: str
    champion_id: str
    patch: str
    last_changed: str

    range_type: RangeType
    resource_type: ResourceType
    hp: float
    hp_per_lvl: int
    mana: float
    mana_per_lvl: float
    movementspeed: int
    armor: int
    armor_per_lvl: float
    mr: float
    mr_per_lvl: float
    attackrange: int
    hp_regen: float
    hp_regen_per_lvl: float
    mana_regen: float
    mana_regen_per_lvl: float
    ad: float
    ad_per_lvl: float
    attackspeed: float
    attackspeed_ratio: float
    attackspeed_per_lvl: float
    attack_windup: float
    windup_modifier: float
    missile_speed: int

    passive: ChampionPassive
    q: ChampionAbility
    w: ChampionAbility
    e: ChampionAbility
    r: ChampionAbility

    ready_to_use: bool = False
    changes: list[str] = []

    image: Image



def test():
    input_string = "2.4 / 2.6 / 2.8 / 3 / 3.2% of target's maximum health"
    regex1 = r"(?P<flats>[\d/ \.]+)(?P<perc>%)?( ?\(\+ (?P<scalings>.*)\))*(?P<stat>[\w' ]*)"
    result = re.fullmatch(regex1, input_string)
    print(result["flats"])
    print(result["stat"])
    if result["scalings"]:
        scals = result["scalings"].split(") (+ ")
        print(scals)



def main():
    test()



if __name__ == "__main__":
    main()