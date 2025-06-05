import pytest

from datetime import datetime

from src.server.loader.helper import RuneClass
from src.server.loader.webscraper2 import (
    scrape_champion,
    _scrape_attackspeed_stats,  
    _scrape_side_box_stats,     
    _scrape_passive,            
    _scrape_passive_description,
    _scrape_ability,            
    _scrape_ability_stats,      
    _scrape_effects,            
    _scrape_effect_paragraph,   
    _scrape_effect_components,  
    _create_effect_component,   
    scrape_item,                
    _scrape_item_class,         
    _scrape_item_elements,      
    _scrape_item_stats,         
    _scrape_item_stat_block,    
    _scrape_item_active,        
    _scrape_item_passives,      
    _scrape_item_element_text,  
    scrape_rune,                
    _scrape_rune_passive,       
    _scrape_rune_summoner_stats,
    scrape_summonerspell,       
    _scrape_summonerspell_active,
    scrape_hotfix_list,         
    scrape_patch,               
    _scrape_patch_only,         
    _scrape_patch_champions,    
    _scrape_patch_champion,     
    _scrape_patch_rest,         
    _scrape_patch_object,       
    _scrape_hotfix,             
    _scrape_hotfix_all,         
    _scrape_hotfix_champion,    
    _scrape_hotfix_object,      
)
from src.server.models.ability import ChampionAbility, Ability, ItemActive
from src.server.models.champion import NewChampion, Champion
from src.server.models.dataenums import RangeType, Stat, ItemClass, EffectType, DamageSubType, DamageProperties, HpScaling
from src.server.models.effect import Effect
from src.server.models.item import NewItem
from src.server.models.rune import NewRune
from src.server.models.json_validation import PassiveJson, Image, SpellJson, ChampionJson, StatsJson, ItemJson, SummonerspellJson, GoldJson, RuneJson
from src.server.models.passive import ChampionPassive, Passive
from src.server.models.summonerspell import NewSummonerspell




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
    assert len(result.r.effects) > 0
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
        ("ahri", ("15.4.1", RangeType.RANGED)),
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
    assert passive.static_cooldown == "30.0 + ((level - 1.0) // 5.0) * -6.0"
    assert passive.description.startswith("Innate: Periodically, Malzahar")  # or similar
    assert "cooldown" not in passive.raw_stats


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
    assert len(ability.effects) == 4
    assert "cooldown" not in ability.raw_stats



def test_scrape_ability_stats_void(load_soup):
    soup = load_soup("malzahar")
    block = soup.find("div", class_="skill skill_w")
    stat_dict = _scrape_ability_stats(block)
    expected_keys = ["cost", "cooldown", "cast time", "target range"]
    assert all(key in stat_dict for key in expected_keys)
    assert stat_dict["cost"] == "40.0 + (rank - 1) * 5.0"
    assert stat_dict["cast time"] == "none"


def test_scrape_effects_nether(load_soup):
    soup = load_soup("malzahar")
    ability_block = soup.find("div", class_="skill skill_r")
    result = _scrape_effects(ability_block)
    assert len(result) == 4
    assert isinstance(result[0], Effect)
    assert result[0].text.startswith("Active: Malzahar")


def test_scrape_effect_paragraph_nether(load_soup):
    soup = load_soup("malzahar")
    ability_block = soup.find("div", class_="skill skill_r")
    paragraphs = ability_block.find_all("div", class_="ability-info-row")
    result = _scrape_effect_paragraph(paragraphs[2])
    assert isinstance(result, Effect)
    assert result.text.startswith("Additionally, a Null Zone")
    assert len(result.effect_components) == 1
    assert result.effect_components[0].type_ == EffectType.DAMAGE


def test_scrape_effect_components_nether(load_soup):
    soup = load_soup("malzahar")
    ability_block = soup.find("div", class_="skill skill_r")
    paragraphs = ability_block.find_all("div", class_="ability-info-row")
    stats = paragraphs[2].find("div", class_="ability-info-stats")
    result = _scrape_effect_components(stats)
    assert len(result) == 1
    assert result[0].type_ == EffectType.DAMAGE
    assert isinstance(result[0].props, DamageProperties)
    assert result[0].props.dmg_sub_type == DamageSubType.MAGIC
    assert result[0].props.hp_scaling == HpScaling.MAX_HP



def test_scrape_item_titanic(load_html):
    item_json = ItemJson(
        name="Titanic Hydra",
        description="Titanic Hydra description",
        colloq="Titanic Hydra colloq",
        plaintext="Titanic Hydra",
        from_=["Ravenous Hydra"],
        into=[],
        image=Image(
            full="Titanic_Hydra.png",
            sprite="item0.png",
            group="item",
            x=0,
            y=0,
            w=48,
            h=48
        ),
        gold=GoldJson(
            base=0,
            purchasable=True,
            total=3000,
            sell=2100
        ),
        tags=["Hydra"],
        maps={
            "11.1": True,
            "11.2": True,
            "11.3": False,
        },
        stats={
            "HP": 600,
            "AD": 40,
        }
    )
    titanic_html = load_html("titanic_hydra")
    item = scrape_item("5421", item_json, titanic_html, patch="15.7.1")
    assert isinstance(item, NewItem)
    assert item.name == "Titanic Hydra"
    assert item.class_ == ItemClass.LEGENDARY
    assert isinstance(item.active, ItemActive)
    assert item.active.name == "Titanic Crescent"
    assert item.passives[0].name == "Cleave"


def test_scrape_item_class_titanic(load_soup):
    soup = load_soup("titanic_hydra")  # loads from html/titanic_hydra.html
    item_class = _scrape_item_class(soup)
    assert item_class == ItemClass.LEGENDARY


def test_scrape_item_elements_titanic(load_soup):
    soup = load_soup("titanic_hydra")
    elements = _scrape_item_elements(soup)
    assert "Stats" in elements
    assert "Recipe" in elements
    assert "Active" in elements
    assert "Passive" in elements
    assert "Limitations" in elements


def test_scrape_item_stats_titanic(load_soup):
    soup = load_soup("titanic_hydra")
    elements = _scrape_item_elements(soup)
    stats, masterwork_stats = _scrape_item_stats(elements["Stats"])
    assert stats[Stat.HP] == 600
    assert stats[Stat.AD] == 40
    assert masterwork_stats[Stat.HP] == 785
    assert masterwork_stats[Stat.AD] == 54.29


def test_scrape_item_active_titanic(load_soup):
    soup = load_soup("titanic_hydra")
    elements = _scrape_item_elements(soup)
    active = _scrape_item_active(elements["Active"])
    assert active.name == "Titanic Crescent"
    assert active.unique == True
    assert active.description.startswith("Your next basic attack")  # or similar


def test_scrape_item_passive_titanic(load_soup):
    soup = load_soup("titanic_hydra")
    elements = _scrape_item_elements(soup)
    passives = _scrape_item_passives(elements["Passive"])
    assert len(passives) == 1
    assert passives[0].name == "Cleave"
    assert passives[0].unique == True
    assert passives[0].description.startswith("Basic attacks")  # or similar


def test_scrape_item_element_text_titanic(load_soup):
    soup = load_soup("titanic_hydra")
    elements = _scrape_item_elements(soup)
    limitations = _scrape_item_element_text(elements["Limitations"])
    assert limitations == "Limited to 1 Hydra item."



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
        row=1
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
    assert result.static_cooldown.startswith("20")
    assert "range" in result.raw_stats


def test_scrape_rune_summoner_stats_comet(load_soup):
    soup = load_soup("arcane_comet")
    item_content = soup.find("div", class_="mw-parser-output")
    result = _scrape_rune_summoner_stats(item_content)
    assert "cooldown" in result
    assert "range" in result
    


def test_scrape_summonerspell_smite(load_html):
    summonerspell_json = SummonerspellJson(
        id="SummonerSmite",
        name="Smite",
        description="Smite description",
        tooltip="Smite tooltip",
        maxrank=1,
        cooldown=[15],
        cooldownBurn="",
        cost=[0],
        costBurn="",
        datavalues={},
        effect=[],
        effectBurn=[],
        vars=[],
        key="11",
        summonerLevel=1,
        modes=["Summoner"],
        costType="",
        maxammo="",
        range=[0],
        rangeBurn="",
        image=Image(
            full="SummonerSmite.png",
            sprite="spell0.png",
            group="spell",
            x=0,
            y=0,
            w=48,
            h=48
        ),
        resource="",
    )
    smite_html = load_html("smite")
    result = scrape_summonerspell(summonerspell_json, smite_html, "15.7.1")
    assert isinstance(result, NewSummonerspell)
    assert result.name == "Smite"
    assert result.ability.name == "Smite"


def test_scrape_summonerspell_active_smite(load_soup):
    soup = load_soup("smite")
    result = _scrape_summonerspell_active(soup)
    assert isinstance(result, Ability)
    assert result.name == "Replace"
    assert result.description.startswith("Deals ")  # or similar
    assert result.cooldown == "15"
    assert result.recharge == "90"




@pytest.mark.parametrize(
    "patch, expected",
    [
        ("v25.06", [datetime(2025, 3, 19), datetime(2025, 3, 20), datetime(2025, 3, 21), datetime(2025, 3, 25)]),

        ("v25.08", []),
    ]
)
def test_scrape_hotfix_list(load_html, patch, expected):
    html = load_html(patch)
    hotfixes = scrape_hotfix_list(html)
    
    assert hotfixes == expected




def test_scrape_patch_champions(load_soup):
    soup = load_soup("v25.06")
    content = soup.find("div", class_="mw-parser-output")

    result = _scrape_patch_champions(content)

    assert isinstance(result, dict)
    assert "changed" in result
    assert "Kai'Sa" in result["changed"]
    assert "Gwen" in result["changed"]


def test_scrape_patch_champion_kaisa(load_soup):
    soup = load_soup("v25.06")
    content = soup.find("div", class_="mw-parser-output")

    hotfix_start = content.find("span", id="Champions").find_parent("h3")

    # Find the <dl> for Gwen
    kaisa_dl = None
    for sibling in hotfix_start.find_next_siblings():
        if sibling.name == "dl" and "Kai'Sa" in sibling.text:
            kaisa_dl = sibling
            break

    assert kaisa_dl is not None

    name, changes = _scrape_hotfix_champion(kaisa_dl)

    assert name == "Kai'Sa"
    assert isinstance(changes, dict)
    assert len(changes) == 2
    assert changes["General"][1].startswith("Base health")
    assert changes["Killer Instinct"][0].startswith("Cooldown")


def test_scrape_patch_rest_items_v25s11(load_soup):
    soup = load_soup("v25.s1.1")
    content = soup.find("div", class_="mw-parser-output")

    results = _scrape_patch_rest(content, "Items")

    assert isinstance(results, dict)
    assert "changed" in results
    assert "new" in results
    assert "deleted" in results

    # Sanity check for changed
    assert "Abyssal Mask" in results["changed"]
    assert "Aegis of the Legion" in results["new"]
    assert "Armored Advance" in results["new"]
    assert "Zephyr" in results["deleted"]


def test_scrape_patch_object_Warmogs(load_soup):
    soup = load_soup("v25.06")
    content = soup.find("div", class_="mw-parser-output")
    item_start = content.find("span", id="Items").find_parent("h3")

    # Find the <dl> for Terminus
    target_dl = None
    for sibling in item_start.find_next_siblings():
        if sibling.name == "dl" and "Warmog's Armor" in sibling.get_text():
            target_dl = sibling
            break

    assert target_dl is not None

    name, changes = _scrape_patch_object(target_dl)

    assert name == "Warmog's Armor"
    assert isinstance(changes, list)
    assert len(changes) == 2
    assert "Combine" in changes[0]



def test_scrape_hotfix_teleport_and_armored_advance(load_soup):
    soup = load_soup("v25.s1.1")
    content = soup.find("div", class_="mw-parser-output")
    hotfix_date = datetime(2025, 1, 10)

    patch_changes = _scrape_hotfix(content, hotfix_date)

    # Check general structure
    assert isinstance(patch_changes, dict)
    assert "champions" in patch_changes
    assert "items" in patch_changes
    assert "runes" in patch_changes
    assert "summonerspells" in patch_changes
    assert "changed" in patch_changes["items"]
    assert "changed" in patch_changes["summonerspells"]

    # Gwen hotfix
    assert "Teleport" in patch_changes["summonerspells"]["changed"]
    teleport_changes = patch_changes["summonerspells"]["changed"]["Teleport"]
    assert isinstance(teleport_changes, list)

    # Armored Advance hotfix
    assert "Armored Advance" in patch_changes["items"]["changed"]
    aa_changes = patch_changes["items"]["changed"]["Armored Advance"]
    assert isinstance(aa_changes, list)


def test_scrape_hotfix_champion_gwen(load_soup):
    soup = load_soup("v25.06")
    content = soup.find("div", class_="mw-parser-output")
    hotfix_start = content.find("span", id="March_19th_Hotfix").find_parent("h3")

    # Find the <dl> for Gwen
    gwen_dl = None
    for sibling in hotfix_start.find_next_siblings():
        if sibling.name == "dl" and "Gwen" in sibling.text:
            gwen_dl = sibling
            break

    assert gwen_dl is not None

    name, changes = _scrape_hotfix_champion(gwen_dl)

    assert name == "Gwen"
    assert isinstance(changes, dict)
    assert len(changes["General"]) == 2
    assert changes["General"][1].startswith("Base armor")


def test_scrape_hotfix_object_armored_advance(load_soup):
    soup = load_soup("v25.s1.1")
    content = soup.find("div", class_="mw-parser-output")
    hotfix_start = content.find("span", id="January_10th_Hotfix").find_parent("h3")

    # Locate the first <dl> after hotfix heading (Armored Advance)
    armored_dl = None
    for sibling in hotfix_start.find_next_siblings():
        if sibling.name == "dl":
            armored_dl = sibling
            break
        elif sibling.name not in ["ul"]:
            break

    assert armored_dl is not None

    name, changes = _scrape_hotfix_object(armored_dl)

    assert name == "Armored Advance"
    assert isinstance(changes, list)
    assert len(changes) == 2
    assert changes[0].startswith("Noxian Endurance base")

