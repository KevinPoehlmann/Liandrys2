import re

from bs4 import BeautifulSoup, Tag
from datetime import datetime
import logging
from unicodedata import normalize

from src.server.loader.helper import info_loader, RuneClass
from src.server.loader.patchexceptions import ScrapeError
from src.server.models.ability import Ability
from src.server.models.champion import NewChampion
from src.server.models.item import NewItem
from src.server.models.passive import Passive
from src.server.models.rune import NewRune
from src.server.models.summonerspell import NewSummonerspell
from src.server.models.json_validation import (
    ChampionJson,
    ItemJson,
    PassiveJson,
    RuneJson,
    SpellJson,
    SummonerspellJson
)
from src.server.models.ability import ChampionAbility
from src.server.models.dataenums import (
    AttackspeedStats,
    ItemClass,
    RangeType,
    ResourceType,
    Skill,
)
from src.server.models.image import Image
from src.server.models.passive import ChampionPassive



debugger = logging.getLogger("debugger")
logger = logging.getLogger("patch_loader")



def get_patch():
    pass



def get_hotfix_list(html: bytes) -> list[datetime]:
    wiki_soup = BeautifulSoup(html, "lxml")
    #patch_content = wiki_soup.find("div", class_="mw-body-content mw-content-ltr")
    hotfix_title = wiki_soup.find(id="Hotfixes")
    hotfix_list = []
    if hotfix_title:
        hotfix_content = hotfix_title.parent
        offset_list = hotfix_title.find_all_next(id=re.compile("Hotfix"))
        for offset in offset_list:
            hotfix = offset.text
            hotfix = hotfix.replace(" Hotfix", "")
            month, day = hotfix.split()
            day = int(day[:-2])
            hotfix = datetime(datetime.now().year, datetime.strptime(month, "%B").month, day)
            hotfix_list.append(hotfix)
    return hotfix_list




def create_champion(champion_json: ChampionJson, champion_wiki: str, patch: str) -> NewChampion:
    champion_soup = BeautifulSoup(champion_wiki, "lxml")
    attackspeed = get_attackspeed_stats(champion_soup, champion_json.stats.attackspeed)
    last_changed, range_type = get_side_box_stats(champion_soup)
    passive = create_passive(champion_soup, champion_json.passive)
    q = create_ability(Skill.Q, champion_json.spells[0])
    w = create_ability(Skill.W, champion_json.spells[1])
    e = create_ability(Skill.E, champion_json.spells[2])
    r = create_ability(Skill.R, champion_json.spells[3])

    champion = NewChampion(
        key=champion_json.key,
        name=champion_json.name,
        champion_id=champion_json.id_,
        patch=patch,
        last_changed=last_changed,
        range_type=range_type,
        resource_type=ResourceType(champion_json.partype),
        hp=champion_json.stats.hp,
        hp_per_lvl=champion_json.stats.hpperlevel,
        mana=champion_json.stats.mp,
        mana_per_lvl=champion_json.stats.mpperlevel,
        movementspeed=champion_json.stats.movespeed,
        armor=champion_json.stats.armor,
        armor_per_lvl=champion_json.stats.armorperlevel,
        mr=champion_json.stats.spellblock,
        mr_per_lvl=champion_json.stats.spellblockperlevel,
        attackrange=champion_json.stats.attackrange,
        hp_regen=champion_json.stats.hpregen,
        hp_regen_per_lvl=champion_json.stats.hpregenperlevel,
        mana_regen=champion_json.stats.mpregen,
        mana_regen_per_lvl=champion_json.stats.mpregenperlevel,
        ad=champion_json.stats.attackdamage,
        ad_per_lvl=champion_json.stats.attackdamageperlevel,
        attackspeed=champion_json.stats.attackspeed,
        attackspeed_ratio=attackspeed.attackspeed_ratio,
        attackspeed_per_lvl=champion_json.stats.attackspeedperlevel,
        attack_windup=attackspeed.attack_windup,
        windup_modifier=attackspeed.windup_modifier,
        missile_speed=attackspeed.missile_speed,
        passive=passive,
        q=q,
        w=w,
        e=e,
        r=r,
        image=champion_json.image
    )
    return champion
    


def get_attackspeed_stats(wiki_soup: BeautifulSoup, attackspeed: float) -> AttackspeedStats:
    attack_speed = wiki_soup.find("aside", class_ = "portable-infobox pi-background pi-border-color pi-theme-stats-table pi-layout-default type-lol-champion")
    as_content = attack_speed.find_all(class_ = "pi-item pi-group pi-border-color")
    as_sq = as_content[1].find_all(class_ = "pi-smart-data-value pi-data-value pi-font pi-item-spacing pi-border-color")
    windup_pair = as_sq[1].contents[1].split("%")

    attackspeed_stats = AttackspeedStats(attackspeed_ratio=attackspeed)

    attackspeed_stats.attack_windup = float(windup_pair[0])   
    windup_mod = windup_pair[1].strip("mod. ()")
    if windup_mod:
        attackspeed_stats.windup_modifier = float(windup_mod)
    if as_sq[2].contents[1] != "N/A":
        attackspeed_stats.attackspeed_ratio = float(as_sq[2].contents[1])
    if len(as_sq) > 4:
        missile_speed =  as_sq[4].contents[1]
        if missile_speed == "Non-projectile":
            missile_speed = -1
        attackspeed_stats.missile_speed = int(missile_speed)

    return attackspeed_stats


def get_side_box_stats(wiki_soup: BeautifulSoup) -> tuple[str, RangeType]:

    infobox = wiki_soup.find("div", id="infobox-champion-container")
    last_changed = infobox.find(class_="pi-item pi-data pi-item-spacing pi-border-color", attrs={"data-source": "changed"})
    last_changed = last_changed.find("a").text
    range_type = infobox.find(class_="pi-item pi-data pi-item-spacing pi-border-color", attrs={"data-source": "rangetype"})
    range_type = range_type.find("a", class_="mw-redirect").text
    range_type = normalize("NFKD", range_type)
    return last_changed[1:] + ".1", RangeType(range_type)


def create_passive(wiki_soup: BeautifulSoup, passive_json: PassiveJson) -> ChampionPassive:
    passive = ChampionPassive(
        name=passive_json.name,
        description=passive_json.description,
        image=passive_json.image
    )
    #TODO work!
    return passive


def create_ability(wiki_soup: BeautifulSoup, ability_json: SpellJson) -> ChampionAbility:
    ability = ChampionAbility(
        name=ability_json.name,
        description=ability_json.description,
        maxrank=ability_json.maxrank,
        image=ability_json.image
    )
    #TODO stuff
    return ability




def create_item(item_id: str, item_json: ItemJson, item_wiki: str, patch: str) -> NewItem:
    item = NewItem(
        item_id=item_id,
        name=item_json.name,
        patch=patch,
        gold=item_json.gold.total,
        into=item_json.into,
        from_=item_json.from_,
        image=item_json.image
    )

    if item_id.startswith("15"):
        item.class_ = ItemClass.TOWER_MINION
        return item
    
    item_soup = BeautifulSoup(item_wiki, "lxml")
    wiki_item = get_item_content(item.name, item_soup)
    if not wiki_item: return item

    item_class = wiki_item.find("a", attrs={"title": re.compile("Category")})
    if not item_class: return item
    try:
        item.class_ = ItemClass(item_class.text)
    except ValueError as e:
        logger.warning(e)
        item.class_ = ItemClass.ERROR

    #TODO a lot more todo here :) !!!
    return item
    


def get_item_content(item_name: str, wiki_soup: BeautifulSoup) -> Tag:
    wiki_item = wiki_soup.find("div", class_="mw-parser-output")
    if not wiki_item: return
    #for Ornn Items
    heading = wiki_soup.find("h1", id="firstHeading").text.strip()
    if heading != item_name:
        wiki_item = wiki_item.find("div", class_="wds-tab__content wds-is-current").nextSibling
    return wiki_item




def create_rune(rune_class: RuneClass, rune_wiki: str, patch: str, image: Image) -> NewRune:
    rune_soup = BeautifulSoup(rune_wiki, "lxml")
    try:
        passive = get_rune_passive(rune_soup)
    except (AttributeError, ValueError) as e:
        raise ScrapeError(e, "Rune", rune_class.rune.name)
    
    passive.name = rune_class.rune.name
    passive.description = rune_class.rune.longDesc

    rune = NewRune(
        rune_id=rune_class.rune.id_,
        name=rune_class.rune.name,
        patch=patch,
        tree=rune_class.tree,
        tree_id=rune_class.tree_id,
        row=rune_class.row,
        passive=passive,
        image=image
    )
    return rune
    


def get_rune_passive(rune_wiki: BeautifulSoup) -> Passive:
    info_box = rune_wiki.find("aside", class_="portable-infobox pi-background pi-border-color pi-theme-rune pi-layout-default")
    rune_content = info_box.find_all("section", class_="pi-item pi-group pi-border-color")
    passive_content = rune_content[2].find_all("div", class_="pi-item pi-data pi-item-spacing pi-border-color")
    passive = Passive(name="replace")
    #TODO some work here as well ;)
    return passive




def create_summonerspell(summonerspell_json: SummonerspellJson, summonerspell_wiki: str, patch: str) -> NewSummonerspell:
    summonerspell_soup = BeautifulSoup(summonerspell_wiki, "lxml")
    try:
        wiki_summonerspell = get_summonerspell_content(summonerspell_soup)
        if wiki_summonerspell:
            ability = create_summonerspell_ability(wiki_summonerspell)
            ability.name = summonerspell_json.name
            ability.description = summonerspell_json.description
        else:
            logger.info(f"Can't find the wiki page for summoner {summonerspell_json.name}")
            ability = Ability(
                name=summonerspell_json.name,
                description=summonerspell_json.description
            )
    except (AttributeError, ValueError) as e:
        raise ScrapeError(e, "Summoner", summonerspell_json.name)
    summonerspell = NewSummonerspell(
        key=summonerspell_json.id_,
        name=summonerspell_json.name,
        patch=patch,
        ability=ability,
        image=summonerspell_json.image
    )
    return summonerspell



def get_summonerspell_content(wiki_soup: BeautifulSoup) -> Tag:
    pass


def create_summonerspell_ability(summonerspell_content: Tag) -> Ability:
    pass
    