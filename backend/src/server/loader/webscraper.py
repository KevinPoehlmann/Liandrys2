import re

from bs4 import BeautifulSoup, Tag
from datetime import datetime
import logging
from unicodedata import normalize

from src.server.loader.helper import info_loader, RuneClass
from src.server.loader.patchexceptions import ScrapeError
from src.server.models.ability import Ability, ItemActive
from src.server.models.champion import NewChampion
from src.server.models.effect import Effect, Scaling, EffectComponent
from src.server.models.item import NewItem
from src.server.models.passive import Passive, ItemPassive
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
    AbilityBaseStats,
    AbilityCosts,
    AbilityDetails,
    AbilityStat,
    AbilityStatKey,
    ActiveType,
    AttackspeedStats,
    Counter,
    CounterEffect,
    CounterType,
    DamageSubType,
    DamageType,
    ItemClass,
    ItemStat,
    Map,
    MinionAggro,
    RangeType,
    ResourceType,
    Skill,
    Stat,
    StatusType,
    Table,
    TableTitle
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
    q = create_ability(Skill.Q, champion_soup, champion_json.spells[0])
    w = create_ability(Skill.W, champion_soup, champion_json.spells[1])
    e = create_ability(Skill.E, champion_soup, champion_json.spells[2])
    r = create_ability(Skill.R, champion_soup, champion_json.spells[3])

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
        windup_modifier=attackspeed.windup_modifier/100,
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
    try:
        ability_content = wiki_soup.find("div", class_="skill skill_innate")
        text_effects = get_ability_text(ability_content)
        splitted_effects = get_ability_splitted_text(ability_content)
        base_stats = get_ability_base_stats(ability_content)
        details = get_ability_details(ability_content)
    except (AttributeError, ValueError) as e:
        raise ScrapeError(e, "Passive", passive.name)

    passive.effects.extend(text_effects)
    passive.effects.extend(splitted_effects)
    passive.ability_stats = base_stats.ability_stats
    passive.damage_sub_type = details.damage_sub_type
    passive.damage_type = details.damage_type
    passive.counters = details.counters
    
    return passive


def create_ability(skill: Skill, wiki_soup: BeautifulSoup, ability_json: SpellJson) -> ChampionAbility:
    ability = ChampionAbility(
        name=ability_json.name,
        description=ability_json.description,
        maxrank=ability_json.maxrank,
        image=ability_json.image
    )
    if ability.name.startswith("Subject: "):
        return ability
    try:
        ability_content = wiki_soup.find("div", class_=str(skill.value))
        text_effects = get_ability_text(ability_content)
        splitted_effects = get_ability_splitted_text(ability_content)
        base_stats = get_ability_base_stats(ability_content)
        details = get_ability_details(ability_content)
    except (AttributeError, ValueError) as e:
        raise ScrapeError(e, "Ability", ability.name)    

    ability.effects.extend(text_effects)
    ability.effects.extend(splitted_effects)
    ability.cast_time = base_stats.cast_time
    ability.cooldown = base_stats.cooldown
    ability.costs = base_stats.costs
    ability.ability_stats = base_stats.ability_stats
    ability.damage_sub_type = details.damage_sub_type
    ability.damage_type = details.damage_type
    ability.counters = details.counters
    
    return ability


def get_ability_text(ability_content: Tag) -> list[Effect]:
    text = ability_content.find_all("div", style="grid-column-end: span 2;")
    effect_list = []
    for paragraph in text:
        effect = get_ability_paragraph(paragraph)
        effect_list.append(effect)
    return effect_list


def get_ability_paragraph(paragraph_content: Tag) -> Effect:
    table_stats = get_paragraph_tables(paragraph_content)      

    effect = Effect(
        text=normalize("NFKD", paragraph_content.text).strip(),
        stat=table_stats
    )
    return effect


def get_paragraph_tables(paragraph_content: Tag) -> list[EffectComponent]:
    table_stats = []
    if paragraph_content.find("span", class_ = "pp-tooltip"):
        #looking for tables in paragraph
        tables = paragraph_content.find_all("span", class_ = "pp-tooltip")
        #TODO check if there is more than 1 at any point
        for value in tables:
            if not value.has_attr("data-bot_values"):
                continue
            effect_stat = EffectComponent()
            for sibling in value.next_siblings:
                if sibling == " ": continue
                effect_stat.comment += sibling.text
            bot_values = value["data-bot_values"]
            if "%" in bot_values:
                bot_values = bot_values.replace("%", "")
                effect_stat.comment += " percent"
            title = re.findall(r"\(based on (.*)\)", value.text)
            if value["data-top_values"]:
                top_values = value["data-top_values"]
                if title:
                    effect_stat.scalings.append(Scaling(value=usify_tables(bot_values, top_values, title=title[0])))
                else:
                    effect_stat.scalings.append(Scaling(value=usify_tables(bot_values, top_values, title="?")))                    
            else:
                effect_stat.scalings.append(Scaling(value=usify_tables(bot_values, title=title[0])))
            table_stats.append(effect_stat)
    return table_stats


def get_ability_splitted_text(ability_content: Tag) -> list[Effect]:
    effect_list = []
    text = ability_content.find_all("div", style="grid-column-end: span 2; display:contents")
    for paragraph in text:
        text_part = paragraph.find("div", style = "vertical-align:top; padding: 0 0 0 7px;").text
        stat_part = paragraph.find("table", style="border-collapse: collapse;")
        stat_keys = stat_part.find_all("dt") #stat
        stat_values = stat_part.find_all("dd") #stat value
        #TODO check for tables in stats
        stats = {}
        for stat_k, stat_v in zip(stat_keys, stat_values):
            stats[stat_k.text.strip(": ")] = normalize("NFKD", stat_v.text)
        usified_stats = usify_stats(stats)
        #checking for tables
        table_stats = get_paragraph_tables(paragraph)
        effect = Effect(
            text = normalize("NFKD", text_part).strip(),
            effect_components=usified_stats+table_stats
        )
        effect_list.append(effect)
    return effect_list



def get_ability_base_stats(ability_content: Tag) -> AbilityBaseStats:
    ability_stats = AbilityBaseStats()
    effect_stats = ability_content.find("section", class_ = "pi-item pi-group pi-border-color")
    if effect_stats:
        stat_list = effect_stats.find_all("div", class_ = "pi-item pi-data pi-item-spacing pi-border-color")
        for effect_stat in stat_list:
            key = effect_stat.find("h3").text.strip(": ")
            value_con = effect_stat.find("div", class_ = "pi-data-value pi-font")
            value = value_con.text
            #checking for tables
            if key == "CAST TIME":
                try:
                    ability_stats.cast_time = float(value)
                except ValueError:
                    ability_stats.ability_stats.append(AbilityStat(key=AbilityStatKey(key), values=value))
                continue
            elif key == "COOLWDOWN":
                ability_stats.cooldown = get_ability_base_table(effect_stat, value)
            elif key == "COST":
                if len(value_con.contents) > 1:
                    unit = value_con.contents[1].text
                    costs = value_con.contents[0].text
                else:
                    cost_pair = value_con.text.rsplit(" ", 1)
                    unit = cost_pair[1]
                    costs = cost_pair[0]
                if "%" in costs:
                    costs = costs.replace("%", "")
                    unit += " percent"
                try:
                    costs = get_ability_base_table(effect_stat, costs)
                except ValueError as e:
                    logger.warning(e)
                    ability_stats.ability_stats.append(AbilityStat(key=AbilityStatKey(key), values=value))
                    continue
                try:
                    ability_stats.costs = AbilityCosts(values=costs, unit=Stat(unit))
                except ValueError as e:
                    logger.warning(e)
                    ability_stats.costs = AbilityCosts(values=costs, unit=Stat.ERROR)
            else:
                try:
                    ability_stats.ability_stats.append(AbilityStat(key=AbilityStatKey(key), values=value))
                except ValueError as e:
                    logger.warning(e)
                    ability_stats.ability_stats.append(AbilityStat(key=AbilityStatKey.ERROR, values=value))

    return ability_stats


def get_ability_base_table(effect_stat: Tag, value: str) -> Table:
    if effect_stat.find("span", class_ = "pp-tooltip"):
        value = get_ability_stat_table(effect_stat)
        return value
    bot = [float(x) for x in value.split(" / ")]
    if len(bot) == 1:
        return Table(bot=bot, top=[1], title=TableTitle.CONST)
    top = list(range(1, len(bot)+1))
    return Table(top=top, bot=bot)


def get_ability_stat_table(table: Tag) -> Table:
    value = table.find("span", class_ = "pp-tooltip")
    if value.has_attr("data-bot_values"):
        bot_values = value["data-bot_values"]
        title = re.findall(r"\(based on (.*)\)", value.text)
        if value["data-top_values"]:
            top_values = value["data-top_values"]
            return usify_tables(bot_str=bot_values, top_str=top_values, title=title[0])
        return usify_tables(bot_str=bot_values, title=title[0])
    

def get_ability_details(ability_content: Tag) -> AbilityDetails:
    details = AbilityDetails()
    effect_types = ability_content.findNext("div", class_="tabbertab-bordered")
    type_list = effect_types.find_all("section", class_="pi-item pi-group pi-border-color")
    for effect_type in type_list:
        type_header = effect_type.find("h2", class_="pi-item pi-header pi-secondary-font pi-item-spacing pi-secondary-background")
        if type_header:
            damage_headers = effect_type.find_all("h3", class_="pi-smart-data-label pi-data-label pi-secondary-font pi-item-spacing pi-border-color")
            damage_types = effect_type.find_all("div", class_="pi-smart-data-value pi-data-value pi-font pi-item-spacing pi-border-color")
            if type_header.text == "Damage type":
                for header, type in zip(damage_headers, damage_types):
                    if header.text == "Sub-type":
                        sub_types = type.find_all("span")
                        details.damage_sub_type = [DamageSubType(sub_type.text) for sub_type in sub_types]
                    elif header.text == "Type":
                        details.damage_type = DamageType(type.text.strip())
                    elif header.text == "Minion Aggro":
                        details.minion_aggro = MinionAggro(type.text.strip())
                    else:
                        logger.warning(f"New Damage type '{header.text}' encountered!")
            elif type_header.text == "Counters":
                for header, type in zip(damage_headers, damage_types):
                    details.counters.append(Counter(
                        type_=CounterType(header.text),
                        effect=CounterEffect(type.text.strip())
                    ))
            else:
                logger.warning(f"New Detail type '{type_header.text}' encountered!")
    return details



def create_item(item_id: str, item_json: ItemJson, item_wiki: str, patch: str, masterwork: bool) -> NewItem:
    
    item = NewItem(
        item_id=item_id,
        name=item_json.name,
        patch=patch,
        gold=item_json.gold.total,
        into=item_json.into,
        from_=item_json.from_,
        image=item_json.image
    )

    try:
        maps = [Map(m) for m, v in item_json.maps.items() if v == True]
        item.maps = maps
    except ValueError as e:
        logger.warning(e)

    if item_id.startswith("15"):
        item.class_ = ItemClass.TOWER_MINION
        return item
    
    item_soup = BeautifulSoup(item_wiki, "lxml")
    wiki_item = get_item_content(item_soup)
    if not wiki_item: return item

    item_class = wiki_item.find("a", attrs={"title": re.compile("Category")})
    if not item_class: return item
    try:
        if masterwork:
            item.class_ = ItemClass.MASTERWORK
        else:
            item.class_ = ItemClass(item_class.text)
    except ValueError as e:
        logger.warning(e)
        item.class_ = ItemClass.ERROR

    elements = get_item_elements(wiki_item)
    for title, content in elements.items():
        match title:
            case "Stats": item.stats = get_item_stats(content, masterwork)
            case "Active": item.active = get_item_active(content)
            case "Passive": item.passives = get_item_passives(content)
            case "Limitations": item.limitations = get_item_limitations(content)
            case "Aura": item.passives.append(get_item_passives(content))
            case "Consume": item.active = get_item_consume(content)
            case "Requirements": item.requirements = get_item_requirements(content)

    return item
    


def get_item_content(wiki_soup: BeautifulSoup) -> Tag:
    wiki_item = wiki_soup.find("div", class_="mw-parser-output")
    if not wiki_item: return
    return wiki_item


def get_item_elements(item_content: Tag) -> dict[Tag]:
    item_info = item_content.find("aside", class_="portable-infobox pi-background pi-border-color pi-theme-wikia pi-layout-stacked")
    info_list = item_info.find_all("section", class_="pi-item pi-group pi-border-color")
    info_dict = {}
    for element in info_list[1:]:
        title = element.find("h2")
        if title:
            info_dict[title.text] = element
    return info_dict


def is_masterwork(item_wiki: str) -> bool:
    item_soup = BeautifulSoup(item_wiki, "lxml")
    wiki_item = get_item_content(item_soup)
    if not wiki_item: return False
    item_class = wiki_item.find("a", attrs={"title": re.compile("Category")})
    if not item_class: return False
    elements = get_item_elements(wiki_item)
    if "Stats" in elements:
        masterwork = elements["Stats"].find("div", text=re.compile("Masterwork Total"))
    else:
        return False
    return bool(masterwork)


def get_item_stats(stat_content: Tag, masterwork: bool) -> dict:
    tabs = stat_content.find_all("div", class_="wds-tab__content")
    if masterwork:
        stats = tabs[2].find_all("div", class_="pi-data-value pi-font")
    else:
        stats = tabs[0].find_all("div", class_="pi-data-value pi-font")
    item_stats = {}
    for stat in stats:
        value = ""
        for content in stat.contents:
            value += content.text
        pair = value.split(maxsplit=1)
        if len(pair) < 2:
            logger.warning(f"Weird Item stat: {value}")
            continue
        if "%" in pair[0]:
            pair[0] = pair[0].strip(" %+")    #value
            pair[1] += " percent"           #unit
        if pair[0] == "+":
            item_stats[Stat.GOLD_P_10] = int(pair[1].split()[0])
            continue
        try:
            item_stats[Stat(pair[1])] = float(pair[0])
        except ValueError as e:
            logger.warning(e)
            item_stats[Stat.ERROR] = float(pair[0])

    return item_stats


def get_item_active(active_content: Tag) -> ItemActive:
    active_wiki = active_content.find("div", class_="pi-data-value pi-font")
    active_title = active_wiki.find("b")
    if active_title:
        active_title = active_title.text
    else:
        active_title = ""
    effect_list = get_effect_list(active_wiki)
    #TODO remove title from text
    active = ItemActive(
        name = active_title,
        type_ = ActiveType.ACTIVE,
        effects = effect_list
    )
    return active


def get_item_passives(passives_content: Tag) -> list[ItemPassive]:
    passive_section = passives_content.find_all("div", class_="pi-data-value pi-font")
    passive_list = []
    for passive in passive_section:
        passive_title = passive.find("b")
        if passive_title:
            passive_title = passive_title.text
        else:
            passive_title = ""
        effect_list = get_effect_list(passive)
        #TODO remove title from text
        name = passive_title.strip(": ")
        unique = "Unique - " in name
        name = name.replace("Unique - ", "")
        passive = ItemPassive(
            name = name.strip(": "),
            effects = effect_list,
            unique=unique
        )
        passive_list.append(passive)
    return passive_list


def get_effect_list(wiki: Tag) -> list[Effect]:
    contents = []
    start = 0
    #effect_content = wiki.find("div", class_="pi-data-value pi-font")
    for i, con in enumerate(wiki.contents):
        #splitting paragraphs
        if con.name == "br":
            contents.append(wiki.contents[start:i])
            start = i+1
    contents.append(wiki.contents[start:])
    effect_list = []
    for content in contents:
        c_string = ""
        for c in content:
            if type(c) is str:
                c_string += c
            else:
                c_string += c.text
        effect = Effect(
            text = normalize("NFKD", c_string)
        )
        effect_list.append(effect)
    return effect_list


def get_item_consume(consume_content: Tag) -> ItemActive:
    consume = consume_content.find("div", class_="pi-data-value pi-font")
    effect = Effect(
        text = normalize("NFKD", consume.text)
    )
    active = ItemActive(
        name = "Consume",
        type_ = ActiveType.CONSUME,
        effects = [effect]
    )
    return active


def get_item_limitations(limitation_content: Tag) -> str:
    limitations = limitation_content.find("div", class_="pi-data-value pi-font")
    return normalize("NFKD", limitations.text)


def get_item_requirements(requirements_content: Tag) -> str:
    requirements = requirements_content.find("div", class_="pi-data-value pi-font")
    return normalize("NFKD", requirements.text)




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
    for passive_section in passive_content:
        data_source = passive_section.attrs["data-source"]
        if "description" in data_source:
            effect = Effect(
                text=normalize("NFKD", passive_section.text).strip()
            )
            tables = passive_section.find_all("span", class_ = "pp-tooltip")
            if tables:
                for value in tables:
                    bot_values = value["data-bot_values"]
                    title = re.findall(r"\(based on (.*)\)", value.text)
                    if not title:
                        title.append("level")
                    flat_table = usify_tables(bot_str=bot_values, title=title[0])
                    effect.effect_components.append(EffectComponent(scalings=[Scaling(value=flat_table)]))
            passive.effects.append(effect)
        else:
            stat = passive_section.find("div", class_="pi-data-value pi-font")
            if stat.find("span", class_ = "pp-tooltip"):
                value = stat.find("span", class_ = "pp-tooltip")
                bot_values = value["data-bot_values"]
            else:
                bot_values=normalize("NFKD", stat.text.strip())
            try:
                passive.ability_stats.append(AbilityStat(key=AbilityStatKey(data_source), values=bot_values))
            except ValueError as e:
                logger.warning(e)
                passive.ability_stats.append(AbilityStat(key=AbilityStatKey.ERROR, values=bot_values))
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
    return wiki_soup.find("aside", class_="portable-infobox pi-background pi-border-color pi-theme-wikia pi-layout-default")


def create_summonerspell_ability(summonerspell_content: Tag) -> Ability:
    ability = Ability(name="replace")
    ability_content = summonerspell_content.find_all("div", class_="pi-item pi-data pi-item-spacing pi-border-color")
    for ability_section in ability_content:
        data_source = ability_section.attrs["data-source"]
        if "effect" in data_source:
            effect = Effect(
                text=normalize("NFKD", ability_section.text).strip()
            )
            if ability_section.find("span", class_ = "pp-tooltip"):
                value = ability_section.find("span", class_ = "pp-tooltip")
                bot_values = value["data-bot_values"]
                title = re.findall(r"\(based on (.*)\)", value.text)
                flat_table = usify_tables(bot_str=bot_values, title=title[0])
                effect.effect_components.append(EffectComponent(scalings=[Scaling(value=flat_table)]))
            ability.effects.append(effect)
        else:
            stat = ability_section.find("div", class_="pi-data-value pi-font")
            try:
                ability.ability_stats.append(AbilityStat(key=AbilityStatKey(data_source), values=normalize("NFKD", stat.text.strip())))
            except ValueError as e:
                logger.warning(e)
                ability.ability_stats.append(AbilityStat(key=AbilityStatKey.ERROR, values=normalize("NFKD", stat.text.strip())))
    return ability
    



def usify_scaling(value: str) -> list[Scaling]:
    result = []
    regex1 = r"(?P<flats>[\d/ \.]+)(?P<perc>%)?( ?\(\+ (?P<scalings>.*)\))*(?P<stat>[\w' ]*)"

    matches = re.fullmatch(regex1, value)
    if not matches:
        logger.warning(f"Scales do not match regex: {value}")
        return [Scaling(value=Table(bot=[1], title=TableTitle.ERROR), stat=Stat.ERROR)]
    if matches["flats"]:
        flat = matches["flats"].split(" / ")
    else:
        logger.error(value)
        logger.error(matches.groups())
        flat = [1]
    bot = [float(item) for item in flat]
    top = list(range(1, len(bot) + 1))
    title = TableTitle.FLAT if len(bot) == 1 else TableTitle.RANK
    try:
        stat = Stat(matches["stat"].strip())
    except ValueError as e:
        logger.warning(e)
        stat = Stat.ERROR
    result.append(Scaling(value=Table(top=top, bot=bot, title=title), stat=stat))

    if matches["scalings"]:
        for scale in matches["scalings"].split(") (+ "):
            scale_res = usify_scaling(scale)
            for sr in scale_res:
                result.append(Scaling(value=sr, stat=stat))
    return result


def usify_stats(input_data: dict[str, str]) -> list[EffectComponent]:
    result = []
    regex1 = r"(?P<flats>[\d/ \.]+)(?P<perc>%)?( ?\(\+ (?P<scalings>.*)\))*(?P<stat>[\w' ]*)"
    
    for key, value in input_data.items():

        scalings = []
        
        matches = re.fullmatch(regex1, value)
        if not matches:
            logger.warning(f"Stats do not match regex: {value}")
            EffectComponent(type_=StatusType.ERROR, comment=key)
            continue
        if matches["flats"]:
            flat = matches["flats"].split(" / ")
        else:
            logger.error(value)
            logger.error(matches.groups())
            flat = [1]
        bot = [float(item) for item in flat]
        top = list(range(1, len(bot) + 1))
        if matches["stat"]:
            try:
                stat = Stat(matches["stat"].strip())
            except ValueError as e:
                logger.warning(e)
                stat = Stat.ERROR
            scalings.append(Scaling(value=Table(top=top, bot=bot), stat=stat))
        else:
            scalings.append(Scaling(value=Table(top=top, bot=bot), stat=Stat.FLAT))

        if matches["scalings"]:
            for scale in matches["scalings"].split(") (+ "):
                scalings.extend(usify_scaling(scale))

        if 'Damage' in key:
            type_ = StatusType.DAMAGE
        elif 'Heal' in key:
            type_ = StatusType.HEAL
        else:
            type_ = StatusType.REPLACE

        status = EffectComponent(scalings=scalings, type_=type_, comment=key)
        result.append(status)

    return result



def usify_tables(bot_str: str, top_str: str = "", title: str = "level") -> Table:
    bot_str = bot_str.replace("th", "").replace("nd", "").strip(";∞")
    bot_values = bot_str.split(";")
    bot_values = list(map(float, bot_values))
    if not top_str:
        top_values = list(range(1, len(bot_values)+1))
    else:
        top_str = top_str.strip(";∞+")
        top_values = top_str.split(";")
        try:
            top_values = list(map(float, top_values))
        except ValueError as e:
            logger.warning(e)
            top_values = list(range(1, len(bot_values)+1))
        if title == "level":
            flat_values=[0]*18
            for top, bot in zip(top_values, bot_values):
                flat_values[int(top)-1:18] = [bot]*(19-int(top))
            bot_values = flat_values
            top_values = list(range(1, len(bot_values)+1))
    try:
        table = Table(top=top_values, bot=bot_values, title=TableTitle(title))
    except ValueError as e:
        logger.warning(e)
        table = Table(top=top_values, bot=bot_values, title=TableTitle.ERROR)
    return table
