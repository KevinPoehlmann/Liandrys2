import pytest
from bs4 import BeautifulSoup


from src.server.loader.helper import RuneClass
from src.server.loader.webscraper2 import (
    scrape_champion,
    _scrape_attackspeed_stats,  
    _scrape_side_box_stats,     
    _scrape_passive,            
    _scrape_passive_description,
    _scrape_ability,            
    _scrape_ability_stats,      
    scrape_rune,                
    _scrape_rune_passive,       
    _scrape_rune_summoner_stats,
)
from src.server.models.ability import ChampionAbility, Ability, ItemActive
from src.server.models.champion import NewChampion, Champion
from src.server.models.enums import RangeType, Stat, ItemClass
from src.server.models.item import NewItem
from src.server.models.rune import NewRune
from src.server.models.json_validation import PassiveJson, Image, SpellJson, ChampionJson, StatsJson, ItemJson, GoldJson, RuneJson
from src.server.models.passive import ChampionPassive, Passive


def test_scrape_champion_malzahar(load_html):
    html = load_html("malzahar")  # from your html test folder

    champion_json = ChampionJson(
        id="Malzahar",
        key="90",
        name="Malzahar",
        title="the Prophet of the Void",
        image=Image(
            full="Malzahar.png",
            sprite="champion0.png",
            group="champion",
            x=0, y=0, w=48, h=48
        ),
        skins=[],
        lore="Void-touched prophet.",
        blurb="A quick blurb.",
        allytips=[],
        enemytips=[],
        tags=["Mage"],
        partype="Mana",
        info={"attack": 2, "defense": 2, "magic": 9, "difficulty": 6},
        stats=StatsJson(
            hp=580, hpperlevel=104, mp=375, mpperlevel=27.5,
            movespeed=335, armor=18, armorperlevel=4.5,
            spellblock=30, spellblockperlevel=1.3,
            attackrange=500, hpregen=6, hpregenperlevel=0.6,
            mpregen=8, mpregenperlevel=0.8,
            crit=0, critperlevel=0,
            attackdamage=55, attackdamageperlevel=3.3,
            attackspeed=0.625, attackspeedperlevel=1.5
        ),
        passive=PassiveJson(
            name="Void Shift",
            description="Placeholder",
            image=Image(
                full="Malzahar_P.png",
                sprite="passive0.png",
                group="passive",
                x=0, y=0, w=48, h=48
            )
        ),
        spells=[
            SpellJson(id="Q", name="Call of the Void", description="", tooltip="", leveltip={}, maxrank=5,
                    cooldown=[6]*5, cooldownBurn="6", cost=[60]*5, costBurn="60", datavalues={}, effect=[], effectBurn=[],
                    vars=[], costType="Mana", maxammo="", range=[900]*5, rangeBurn="900", image=Image(full="Q.png", sprite="", group="spell", x=0, y=0, w=48, h=48), resource="Mana"),
            SpellJson(id="W", name="Void Swarm", description="", tooltip="", leveltip={}, maxrank=5,
                    cooldown=[8]*5, cooldownBurn="8", cost=[40]*5, costBurn="40", datavalues={}, effect=[], effectBurn=[],
                    vars=[], costType="Mana", maxammo="", range=[800]*5, rangeBurn="800", image=Image(full="W.png", sprite="", group="spell", x=0, y=0, w=48, h=48), resource="Mana"),
            SpellJson(id="E", name="Malefic Visions", description="", tooltip="", leveltip={}, maxrank=5,
                    cooldown=[14]*5, cooldownBurn="14", cost=[60]*5, costBurn="60", datavalues={}, effect=[], effectBurn=[],
                    vars=[], costType="Mana", maxammo="", range=[650]*5, rangeBurn="650", image=Image(full="E.png", sprite="", group="spell", x=0, y=0, w=48, h=48), resource="Mana"),
            SpellJson(id="R", name="Nether Grasp", description="", tooltip="", leveltip={}, maxrank=3,
                    cooldown=[140, 110, 80], cooldownBurn="140/110/80", cost=[100]*3, costBurn="100", datavalues={}, effect=[], effectBurn=[],
                    vars=[], costType="Mana", maxammo="", range=[700]*3, rangeBurn="700", image=Image(full="R.png", sprite="", group="spell", x=0, y=0, w=48, h=48), resource="Mana"),
        ],
        recommended=[]
    )

    result = scrape_champion(champion_json, html, patch="15.7.1")
    assert isinstance(result, NewChampion)
    assert result.name == "Malzahar"
    assert result.q.name == "Call of the Void"
    assert result.r.name == "Nether Grasp"
    assert result.r.cooldown != "0"


@pytest.mark.parametrize(
    "champion, base_as, expected",
    [
        ("ahri", 0.668, {"ratio": 0.625, "windup": 0.2, "modifier": 1.0, "missile": 1750}),
        ("taric", 0.625, {"ratio": 0.625, "windup": 0.18, "modifier": 0.25, "missile": 0}),
    ]
)
def test_scrape_attackspeed_stats(champion, base_as, expected, load_soup):
    soup = load_soup(champion)
    stats = _scrape_attackspeed_stats(soup, base_as, champion)

    assert stats.attackspeed_ratio == expected["ratio"]
    assert stats.attack_windup == expected["windup"]
    assert stats.windup_modifier == expected["modifier"]
    assert stats.missile_speed == expected["missile"]


@pytest.mark.parametrize(
    "champion, expected",
    [
        ("ahri", ("15.8.1", RangeType.RANGED)),
        ("taric", ("14.21.1", RangeType.MELEE)),
    ]
)
def test_scrape_side_box_stats(champion, expected, load_soup):
    soup = load_soup(champion)
    last_changed, range_type = _scrape_side_box_stats(soup, champion)

    assert last_changed == expected[0]
    assert range_type == expected[1]


def test_scrape_passive_malzahar(load_soup):
    soup = load_soup("malzahar")
    passive_json = PassiveJson(
        name= "Void Shift",
        description="Void Shift Text",
        image= Image(
            full= "Malzahar_P.png",
            sprite= "passive0.png",
            group= "passive",
            x= 0,
            y= 0,
            w= 48,
            h= 48
        )
    )

    passive = _scrape_passive(soup, passive_json, champion_name="Malzahar")

    assert isinstance(passive, ChampionPassive)
    assert passive.name == "Void Shift"
    assert passive.raw_stats["static cooldown"] == "30.0 + ((level - 1.0) // 5.0) * -6.0"
    assert passive.description.startswith("Innate: Periodically, Malzahar")  # or similar


def test_scrape_ability_malzahar(load_soup):
    soup = load_soup("malzahar")
    spell_json = SpellJson(
        id="MalzaharR",
        name="Nether Grasp",
        description="Malzahar suppresses the target and channels a damaging void beam for 2.5 seconds.",
        tooltip="Malzahar suppresses the target and channels a damaging void beam for 2.5 seconds.",
        leveltip={},
        maxrank=3,
        cooldown=[140, 110, 80],
        cooldownBurn="140/110/80",
        cost=[100, 100, 100],
        costBurn="100",
        datavalues={},
        effect=[],
        effectBurn=[],
        vars=[],
        costType="Mana",
        maxammo="",
        range=[700, 700, 700],
        rangeBurn="700",
        image=Image(
            full="MalzaharR.png",
            sprite="spell0.png",
            group="spell",
            x=0,
            y=0,
            w=48,
            h=48
        ),
        resource="Mana"
    )
    ability = _scrape_ability("r", soup, spell_json, "Malzahar")

    assert isinstance(ability, ChampionAbility)
    assert ability.name == "Nether Grasp"
    assert ability.cooldown == "140.0 + (rank - 1) * -30.0"
    assert ability.description.startswith("Malzahar suppresses")  # or similar
    assert "cooldown" not in ability.raw_stats


def test_scrape_ability_stats_void(load_soup):
    soup = load_soup("malzahar")
    block = soup.find("div", class_="skill skill_w")
    stat_dict = _scrape_ability_stats(block)
    expected_keys = ["cost", "cooldown", "cast time", "target range"]
    assert all(key in stat_dict for key in expected_keys)
    assert stat_dict["cost"] == "40.0 + (rank - 1) * 5.0"
    assert stat_dict["cast time"] == "none"


def test_scrape_rune_comet(load_html):
    rune_class = RuneClass(
        rune=RuneJson(
            id=13,
            key="Sorcery",
            icon="Sorcery.png",
            name="Arcane Comet",
            shortDesc="nah",
            longDesc="fuck you",
        ),
        tree="Sorcery",
        tree_id=2,
        row=1,
        slot=0
    )
    image = Image(
        full="arcane_comet.png",
        group="rune"
    )
    comet_html = load_html("arcane_comet")
    result = scrape_rune(rune_class, comet_html, image, "15.7.1")
    assert isinstance(result, NewRune)
    assert result.name == "Arcane Comet"
    assert result.passive.name == "Arcane Comet"


def test_scrape_rune_passive_comet(load_soup):
    soup = load_soup("arcane_comet")
    result = _scrape_rune_passive(soup)
    assert isinstance(result, Passive)
    assert result.name == "Replace"
    assert result.description.startswith("Dealing ability damage")
    assert result.raw_stats["cooldown"].startswith("20")
    assert "range" in result.raw_stats


def test_scrape_rune_summoner_stats_comet(load_soup):
    soup = load_soup("arcane_comet")
    item_content = soup.find("div", class_="mw-parser-output")
    result = _scrape_rune_summoner_stats(item_content)
    assert "cooldown" in result
    assert "range" in result
    


