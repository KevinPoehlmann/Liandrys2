import locale
import logging
import re
import unicodedata

from bs4 import BeautifulSoup, Tag
from datetime import datetime
from src.server.loader.helper import (
    wiki_to_riot_patch,
    RuneClass,
    parse_formula_from_table,
    parse_formula_from_string,
    parse_effect_formula,
    find_label,
    wiki_to_datetime,
    datetime_to_wiki
)
from src.server.loader.patchexceptions import ScrapeError
from src.server.models.ability import ChampionAbility, ItemActive, Ability
from src.server.models.champion import NewChampion
from src.server.models.dataenums import (
    ActiveType,
    ResourceType,
    RangeType,
    AttackspeedStats,
    AbilityStat,
    ShieldProperties,
    HealProperties,
    DamageSubType,
    DamageProperties,
    EffectType,
    HpScaling,
    ItemClass,
    Map,
    Stat
)
from src.server.models.effect import Effect, EffectComponent
from src.server.models.image import Image
from src.server.models.item import NewItem
from src.server.models.json_validation import ChampionJson, SpellJson, PassiveJson, ItemJson, SummonerspellJson
from src.server.models.passive import ChampionPassive, ItemPassive, Passive
from src.server.models.rune import NewRune
from src.server.models.summonerspell import NewSummonerspell



patch_logger = logging.getLogger("liandrys.patch")



def scrape_champion(champion_json: ChampionJson, wiki_html: str, patch: str, hotfix: datetime | None = None) -> NewChampion | None:
    soup = BeautifulSoup(wiki_html, "lxml")

    # Wiki-only data
    try:
        attackspeed = _scrape_attackspeed_stats(soup, champion_json.stats.attackspeed, champion_json.name)
        last_changed, range_type = _scrape_side_box_stats(soup, champion_json.name)

        # Abilities
        passive = _scrape_passive(soup, champion_json.passive, champion_json.name)
        q = _scrape_ability("Q", soup, champion_json.spells[0], champion_json.name)
        w = _scrape_ability("W", soup, champion_json.spells[1], champion_json.name)
        e = _scrape_ability("E", soup, champion_json.spells[2], champion_json.name)
        r = _scrape_ability("R", soup, champion_json.spells[3], champion_json.name)
    except ScrapeError as e:
        patch_logger.error(f"[CHAMPION] [SCRAPE] [{champion_json.name}] : {e.reason}")
        return None  # skip this champion
    except (AttributeError, ValueError, TypeError) as e:
        patch_logger.error(f"[CHAMPION] [SCRAPE] [{champion_json.name}] : {e}")
        return None
    except Exception as e:
        raise

    # Construct Champion
    champ = NewChampion(
        key=champion_json.key,
        name=champion_json.name,
        champion_id=champion_json.id_,
        patch=patch,
        hotfix=hotfix,
        last_changed=last_changed,
        range_type=range_type,
        resource_type=ResourceType.from_str(champion_json.partype),

        # From Riot API
        hp=champion_json.stats.hp,
        hp_per_lvl=champion_json.stats.hpperlevel,
        mana=champion_json.stats.mp,
        mana_per_lvl=champion_json.stats.mpperlevel,
        ad=champion_json.stats.attackdamage,
        ad_per_lvl=champion_json.stats.attackdamageperlevel,
        armor=champion_json.stats.armor,
        armor_per_lvl=champion_json.stats.armorperlevel,
        mr=champion_json.stats.spellblock,
        mr_per_lvl=champion_json.stats.spellblockperlevel,
        movementspeed=champion_json.stats.movespeed,
        attackrange=champion_json.stats.attackrange,
        hp_regen=champion_json.stats.hpregen,
        hp_regen_per_lvl=champion_json.stats.hpregenperlevel,
        mana_regen=champion_json.stats.mpregen,
        mana_regen_per_lvl=champion_json.stats.mpregenperlevel,
        attackspeed=champion_json.stats.attackspeed,
        attackspeed_ratio=attackspeed.attackspeed_ratio,
        attackspeed_per_lvl=champion_json.stats.attackspeedperlevel / 100,
        attack_windup=attackspeed.attack_windup,
        windup_modifier=attackspeed.windup_modifier / 100,
        missile_speed=attackspeed.missile_speed,

        passive=passive,
        q=q,
        w=w,
        e=e,
        r=r,
        validated=False,
        changes=[],
        image=champion_json.image
    )

    return champ




def _scrape_attackspeed_stats(soup: BeautifulSoup, base_as: float, name: str) -> AttackspeedStats:
    stats = AttackspeedStats(
        attackspeed_ratio=base_as,
        attack_windup=0.0,
        windup_modifier=1.0,
        missile_speed=0
    )

    # Find "Attack speed" header
    headers = soup.find_all("div", class_="infobox-header")
    for h in headers:
        if "attack speed" in h.get_text(strip=True).lower():
            header = h
            break
    else:
        raise ScrapeError("Attack speed section not found", type="Champion", name=name)

    section = header.find_next_sibling("div", class_="infobox-section-two-cell")
    rows = section.find_all("div", class_="infobox-data-row")

    for row in rows:
        label = row.find("div", class_="infobox-data-label")
        value = row.find("div", class_="infobox-data-value")
        if not label or not value:
            continue

        label_text = label.get_text(strip=True).lower()
        value_text = value.get_text(strip=True).lower()

        if "windup" in label_text:
            windup_stats = value_text.split(maxsplit=1)
            windup = windup_stats[0].strip(" %")
            stats.attack_windup = float(windup) / 100
            if len(windup_stats) > 1:
                windup_mod = windup_stats[1].strip(" ()mod.")
                stats.windup_modifier = float(windup_mod)
        elif "as ratio" in label_text and value_text != "n/a":
            stats.attackspeed_ratio = float(value_text)
        elif "missile" in label_text and "non-projectile" not in value_text:
            stats.missile_speed = int(value_text)

    return stats


def _scrape_side_box_stats(soup: BeautifulSoup, name: str) -> tuple[str, RangeType]:
    last_changed = "unknown"
    range_type = RangeType.MELEE  # default fallback

    labels = soup.find_all("div", class_="infobox-data-label")
    for label in labels:
        text = label.get_text(strip=True).lower()
        value = label.find_next_sibling("div", class_="infobox-data-value")
        if not value:
            continue

        if "last changed" in text:
            last_changed = value.get_text(strip=True)
            last_changed = wiki_to_riot_patch(last_changed)
        elif "range type" in text:
            range_text = value.get_text(strip=True).lower()
            if "ranged" in range_text:
                range_type = RangeType.RANGED
            elif "melee" not in range_text:
                raise ScrapeError(f"Unknown range type value: '{range_text}'", type="Champion", name=name)

    return last_changed, range_type



def _scrape_passive(soup: BeautifulSoup, passive_json: PassiveJson, champion_name: str) -> ChampionPassive:
    passive_block = soup.find("div", class_="skill skill_innate")
    if not passive_block:
        raise ScrapeError("Passive block not found", type="champion", name=champion_name)

    stats = _scrape_ability_stats(passive_block)
    description = _scrape_passive_description(passive_block)

    return ChampionPassive(
        name=passive_json.name,
        description=description,
        static_cooldown=stats.pop("static cooldown", "0"),
        image=passive_json.image,
        effects=[],
        raw_stats=stats,
        validated=False,
        changes=[]
    )


def _scrape_passive_description(block: Tag) -> str:
    description = block.find("div", class_="ability-info-content")
    return _get_clean_text(description)


def _scrape_ability(letter: str, soup: BeautifulSoup, spell_json: SpellJson, champion_name: str) -> ChampionAbility:
    if champion_name.lower() == "hwei":
        return _get_hwei_ability(spell_json)
    ability_block = soup.find("div", class_="skill skill_" + letter.lower())
    if not ability_block:
        raise ScrapeError(f"{letter} block not found", type="champion", name=champion_name)

    stats = _scrape_ability_stats(ability_block)

    cooldown = stats.pop("cooldown", "0")
    cost = stats.pop("cost", "0")
    recharge = stats.pop("recharge", "0")

    effects = _scrape_effects(ability_block)


    ability = ChampionAbility(
        name=spell_json.name,
        description=spell_json.description,
        cost=cost,
        cooldown=cooldown,
        recharge=recharge,
        raw_stats=stats,
        image=spell_json.image,
        maxrank=spell_json.maxrank,
        effects=effects,
        validated=False,
        changes=[]
    )

    return ability


def _get_hwei_ability(spell_json: SpellJson) -> ChampionAbility:
    ability = ChampionAbility(
        name=spell_json.name,
        description=spell_json.description,
        image=spell_json.image,
        maxrank=spell_json.maxrank,

        validated=False,
        changes=[]
    )

    return ability

    

def _scrape_ability_stats(block: Tag) -> dict[str, str]:
    stats: dict[str, str] = {}
    stat_blocks = block.find_all("div", class_="ability-info-stats__stat")

    for stat_block in stat_blocks:
        label_tag = stat_block.find("div", class_="ability-info-stats__stat-label")
        value_tag = stat_block.find("div", class_="ability-info-stats__stat-value")
        if not label_tag or not value_tag:
            continue

        label = label_tag.get_text(strip=True).lower().strip(":")
        value = value_tag.get_text(strip=True).lower()

        value_scale = value.split("(", maxsplit=1)
        value = value_scale[0].strip()
        scale = "rank"
        if len(value_scale) > 1:
            scale = value_scale[1].strip(")")
            scale = scale.replace("based on", "").strip()
        span = value_tag.find("span")
        if span and span.has_attr("data-bot_values") and span.has_attr("data-top_values"):
            try:
                top_values = span["data-top_values"]
                bot_values = span["data-bot_values"]
                formula = parse_formula_from_table(bot_str=bot_values, top_str=top_values, scale=scale)
            except Exception as e:
                formula = value
        else:
            formula = parse_formula_from_string(value, scale=scale)
        stats[label] = formula

    return stats


def _scrape_effects(block: Tag) -> list[Effect]:
    paragraphs = block.find_all("div", class_="ability-info-row")
    effects = []
    for paragraph in paragraphs:
        effect = _scrape_effect_paragraph(paragraph)
        if effect:
            effects.append(effect)
    return effects


def _scrape_effect_paragraph(paragraph: Tag) -> Effect:
    just_text = paragraph.find("div", class_="ability-info-description no-stats")
    if just_text:
        text = _get_clean_text(just_text)
        return Effect(text=text)
    text = paragraph.find("div", class_="ability-info-description")
    if text:
        text = _get_clean_text(text)
        effect = Effect(text=text)
        stats = paragraph.find("div", class_="ability-info-stats")
        if stats:
            effect.effect_components = _scrape_effect_components(stats)
        return effect
    return Effect(text="No text found")




def _scrape_effect_components(block: Tag) -> list[EffectComponent]:
    stats = block.find_all("dl", class_="skill-tabs")
    components = []
    for stat in stats:
        label_tag = stat.find("dt")
        values = stat.find("dd")
        if not label_tag or not values:
            continue

        label = label_tag.find("b")
        if not label:
            continue
        text = values.find(string=True, recursive=False)
        text = text.strip() if text else ""
        
        try:
            effect_type, damage_subtype = find_label(_get_clean_text(label))
        except ScrapeError as e:
            patch_logger.warning(f"[CHAMPION] [SCRAPE] [?] Could not find label {label}: {e.reason}")
            continue

        formula, hp_scaling = parse_effect_formula(text)

        spans = values.find_all("span", recursive=False)
        for span in spans:
            if span.has_attr("data-bot_values"):
                top_values = span.get("data-top_values")
                bot_values = span.get("data-bot_values")
                try:
                    formula += f" + {parse_formula_from_table(bot_str=bot_values, top_str=top_values)}"
                except Exception as e:
                    patch_logger.warning(f"[CHAMPION] [SCRAPE] [?] Could not parse formula from table: {span.get_text(strip=True)}")
                    formula += f" + {span.get_text(strip=True)}"
            else:
                span_text = _get_clean_text(span)
                span_formula, span_hp_scaling = parse_effect_formula(span_text)

                if span_hp_scaling != hp_scaling:
                    span_effect_component = _create_effect_component(
                        effect_type=effect_type,
                        formula=span_formula,
                        hp_scaling=span_hp_scaling,
                        damage_subtype=damage_subtype
                    )
                    if span_effect_component:
                        components.append(span_effect_component)
                    continue

                formula += f" + {span_formula}"

        if formula:
            effect_component = _create_effect_component(
                effect_type=effect_type,
                formula=formula,
                hp_scaling=hp_scaling,
                damage_subtype=damage_subtype
            )
            if effect_component:
                components.append(effect_component)
        
    return components


def _create_effect_component(effect_type: EffectType, formula: str, hp_scaling: HpScaling, damage_subtype: DamageSubType) -> EffectComponent | None:
    match effect_type:
        case EffectType.DAMAGE:
            effect_prop = DamageProperties(
                scaling=formula,
                dmg_sub_type=damage_subtype,
                hp_scaling=hp_scaling
            )
        case EffectType.HEAL:
            effect_prop = HealProperties(
                scaling=formula,
                hp_scaling=hp_scaling
            )
        case EffectType.SHIELD:
            effect_prop = ShieldProperties(
                scaling=formula,
                duration=0,
                dmg_sub_type=damage_subtype,
                hp_scaling=hp_scaling
            )
        case _:
            return None
        
    return EffectComponent(
        type_=effect_type,
        props=effect_prop,
        duration=0.0,
        interval=0.0,
        delay=0.0,
        speed=0,
        comment="",
    )



def scrape_item(item_id: str, item_json: ItemJson, wiki_html: str, patch: str, hotfix: datetime | None = None) -> NewItem:
    
    item = NewItem(
        item_id=item_id,
        name=item_json.name,
        patch=patch,
        hotfix=hotfix,
        gold=item_json.gold.total,
        into=item_json.into,
        from_=item_json.from_,
        image=item_json.image
    )

    try:
        maps = [Map.from_str(m) for m, v in item_json.maps.items() if v == True]
        item.maps = maps
    except ValueError as e:
        patch_logger.warning(f"[ITEM] [SCRAPE] [{item.name}] Could not find Map: {e}")

    if item_id.startswith("15"):
        item.class_ = ItemClass.TOWER_MINION
        return item
    
    soup = BeautifulSoup(wiki_html, "lxml")
    item_class = _scrape_item_class(soup)
    if not item_class or item_class == ItemClass.OUTDATED:
        patch_logger.warning(f"[ITEM] [SCRAPE] [{item.name}] Could not find ItemClass, setting to ERROR")
        return item
    item.class_ = item_class

    elements = _scrape_item_elements(soup)
    for title, content in elements.items():
        match title:
            case "Stats":
                stats, masterwork_stats = _scrape_item_stats(content)
                item.stats = stats
                if masterwork_stats:
                    item.masterwork = masterwork_stats
            case "Active":
                item.active = _scrape_item_active(content)
                item.validated = False
            case "Passive":
                item.passives = _scrape_item_passives(content)
                item.validated = False
            case "Limitations":
                item.limitations = _scrape_item_element_text(content)
                item.validated = False
            case "Consume":
                item.active = _create_consume_active(item.name, content)
                item.validated = False
            case "Requirements":
                item.requirements = _scrape_item_element_text(content)
                item.validated = False

    return item

def _scrape_item_class(soup: BeautifulSoup) -> ItemClass | None:
    wiki_item = soup.find("div", class_="mw-parser-output")
    if not wiki_item:
        return None
    wiki_class = wiki_item.find("a", attrs={"title": re.compile("Category")}) # type: ignore[arg-type]
    if not wiki_class:
        return None
    try:
        item_class = ItemClass.from_str((_get_clean_text(wiki_class)))
    except ValueError as e:
        patch_logger.warning(f"[ITEM] [SCRAPE] [?] Could not find ItemClass: {e}")
        item_class = ItemClass.ERROR
    return item_class
    

def _scrape_item_elements(soup: BeautifulSoup) -> dict[str, Tag]:
    item_content = soup.find("div", class_="mw-parser-output")
    item_info = item_content.find("div", class_="infobox") # type: ignore[arg-type]
    headers = item_info.find_all("div", class_="infobox-header")
    info_dict = {header.text: header.next_sibling for header in headers}
    return info_dict


def _scrape_item_stats(content: Tag) -> tuple[dict[Stat, float], dict[Stat, float]]:

    all_stats = content.find_all("div", class_="infobox-section-stacked")
    if not all_stats:
        return {}, {}
    item_stats = _scrape_item_stat_block(all_stats[0])

    masterwork_stats = {}
    if len(all_stats) == 3:
        masterwork_stats = _scrape_item_stat_block(all_stats[2])

    return item_stats, masterwork_stats


def _scrape_item_stat_block(block: Tag) -> dict[Stat, float]:
    parsed_stats = {}
    for stat in block.find_all("div", class_="infobox-data-value"):
        value = stat.text
        pair = value.split(maxsplit=1)
        if len(pair) < 2:
            patch_logger.warning(f"[ITEM] [SCRAPE] [?] Could not parse Item stat: {value}")
            continue
        if "%" in pair[0]:
            pair[0] = pair[0].strip(" %+")
            pair[1] += " percent"
        if pair[0] == "+":
            parsed_stats[Stat.GOLD_P_10] = int(pair[1].split()[0])
            continue
        try:
            parsed_stats[Stat.from_str(pair[1])] = float(pair[0])
        except ValueError as e:
            patch_logger.warning(f"[ITEM] [SCRAPE] [?] Could not parse Item stat: {pair[1]} with value {pair[0]}")
            parsed_stats[Stat.ERROR] = float(pair[0])
    return parsed_stats
    


def _scrape_item_active(content: Tag) -> ItemActive:
    active = ItemActive(
        name="",
        type_=ActiveType.ACTIVE
    )
    title = content.find("b").text
    active.description = _get_clean_text(content, remove=title)
    if "Unique" in title:
        active.unique = True
        title = title.replace("Unique – ", "")
    active.name = title.strip(":")
    return active


def _scrape_item_passives(content: Tag) -> list[ItemPassive]:
    passives = []
    passives_wiki = content.find_all("div", class_="infobox-data-value")
    for passive_wiki in passives_wiki:
        passive = ItemPassive(
            name="",
        )
        title = passive_wiki.find("b").text
        passive.description = _get_clean_text(passive_wiki, remove=title)
        if "Unique" in title:
            passive.unique = True
            title = title.replace("Unique – ", "")
        passive.name = title.strip(":")
        passives.append(passive)
    return passives


def _create_consume_active(name: str, content: Tag) -> ItemActive:
    active = ItemActive(
        name=name,
        type_=ActiveType.CONSUME
    )
    description = _scrape_item_element_text(content)
    active.description = description
    return active


def _scrape_item_element_text(content: Tag) -> str:
    element = content.find("div", class_="infobox-data-value")
    if element:
        return _get_clean_text(element)
    return ""




def scrape_rune(rune_class: RuneClass, wiki_html: str, image: Image, patch: str, hotfix: datetime | None = None) -> NewRune:
    soup = BeautifulSoup(wiki_html, "lxml")
    try:
        passive = _scrape_rune_passive(soup)
    except (AttributeError, ValueError) as e:
        raise ScrapeError(e, "Rune", rune_class.rune.name)
    

    passive.name = rune_class.rune.name

    rune = NewRune(
        rune_id=rune_class.rune.id_,
        name=rune_class.rune.name,
        patch=patch,
        hotfix=hotfix,
        tree=rune_class.tree,
        tree_id=rune_class.tree_id,
        row=rune_class.row,
        passive=passive,
        image=image
    )
    return rune



def _scrape_rune_passive(soup: BeautifulSoup) -> Passive:
    rune_content = soup.find("div", class_="mw-parser-output")
    rune_info = rune_content.find("div", class_="infobox-section") # type: ignore[arg-type]
    passive_text = _get_clean_text(rune_info, remove="Passive:")
    passive_stats = _scrape_rune_summoner_stats(rune_content)
    passive = Passive(
        name="Replace",
        description = passive_text,
        static_cooldown=passive_stats.pop("cooldown", "0"),
        raw_stats=passive_stats
    )
    return passive


def _scrape_rune_summoner_stats(rune_content: Tag) -> dict[str, str]:
    stats = {}
    rune_stats = rune_content.find("div", class_="infobox-section-column")
    if not rune_stats:
        return stats
    stat_list = rune_stats.find_all("div", class_="infobox-data-row")
    for stat in stat_list:
        label = stat.find("div", class_="infobox-data-label")
        value = stat.find("div", class_="infobox-data-value")
        if not label or not value:
            continue
        label_text = label.text.lower()
        value_text = value.text
        stats[label_text] = value_text
    return stats



def scrape_summonerspell(summonerspell_json: SummonerspellJson, wiki_html: str, patch: str, hotfix: datetime | None = None) -> NewSummonerspell:
    soup = BeautifulSoup(wiki_html, "lxml")
    maps = []
    for mode in summonerspell_json.modes:
        try:
            maps.append(Map.from_str(mode))
        except ValueError as e:
            continue
    try:
        active = _scrape_summonerspell_active(soup)
    except AttributeError as e:
        if Map.SR in maps:
            raise ScrapeError(e, "Summonerspell", summonerspell_json.name)
        active = Ability(name=summonerspell_json.name)
    except ValueError as e:
        raise ScrapeError(e, "Summonerspell", summonerspell_json.name)
    
    active.name = summonerspell_json.name

    summonerspell = NewSummonerspell(
        key=summonerspell_json.id_,
        name=summonerspell_json.name,
        patch=patch,
        hotfix=hotfix,
        ability=active,
        maps=maps,
        image=summonerspell_json.image
    )


    return summonerspell


def _scrape_summonerspell_active(soup: BeautifulSoup) -> Ability:
    summonerspell_content = soup.find("div", class_="mw-parser-output")
    summonerspell_info = summonerspell_content.find("div", class_="infobox-section") # type: ignore[arg-type]
    passive_text = summonerspell_info.text
    passive_stats = _scrape_rune_summoner_stats(summonerspell_content)
    active = Ability(
        name="Replace",
        description = passive_text,
        cooldown=passive_stats.pop("cooldown", "0").strip(" seconds"),
        recharge=passive_stats.pop("recharge time", "0").strip(" seconds"),
        raw_stats=passive_stats
    )
    return active

    



def scrape_hotfix_list(wiki_html: str) -> list[datetime]:
    soup = BeautifulSoup(wiki_html, "lxml")
    hotfix_list = []
    patch_block = soup.find("div", class_="mw-parser-output")
    titles = patch_block.find_all("h2")
    for title in titles:
        if "Hotfixes" in title.text:
            break
    else:
        return []
    
    nav_list = patch_block.find_all("li", class_="toclevel-1")
    for topics in nav_list:
        if "Hotfixes" in topics.text:
            hotfixes = topics.find_all("li")
            for hotfix in hotfixes:
                date = hotfix.find("span", class_="toctext")
                if date:
                    hotfix_date = wiki_to_datetime(date.text)
                    hotfix_list.append(hotfix_date)

    return hotfix_list



def scrape_patch(wiki_html: str, hotfix: datetime | None = None) -> dict[str, dict]:
    soup = BeautifulSoup(wiki_html, "lxml")
    content = soup.find("div", class_="mw-parser-output")
    if hotfix is None:
        return _scrape_patch_only(content)
    else:
        return _scrape_hotfix(content, hotfix)



def _scrape_patch_only(content: Tag) -> dict[str, dict]:
    patch_changes = {}
    patch_changes["champions"] = _scrape_patch_champions(content)
    patch_changes["items"] = _scrape_patch_rest(content, "Items")
    patch_changes["runes"] = _scrape_patch_rest(content, "Runes")
    patch_changes["summonerspells"] = _scrape_patch_rest(content, "Summonerspells")
    return patch_changes


def _scrape_patch_champions(content: Tag) -> dict:
    champion_start = content.find("span", id="Champions")
    champion_changes = {"new": [], "changed": {}}
    if not champion_start:
        return champion_changes
    
    champion_start = champion_start.find_parent("h3")
    for sibling in champion_start.find_next_siblings():
        if sibling.name == "dl":
            name, changes = _scrape_patch_champion(sibling)
            if changes is None:
                champion_changes["new"].append(name)
            else:
                champion_changes["changed"][name] = changes
        elif sibling.name == "ul":
            continue
        else:
            break
    
    return champion_changes
                


def _scrape_patch_champion(content: Tag) -> tuple[str, dict | None]:
    if " - New Champion" in content.text:
        champion_name = _get_clean_text(content, remove=" - New Champion")
        return champion_name, None
    
    champion_name = _get_clean_text(content)
    changes = {}
    ul = content.find_next_sibling()
    if not ul:
        return champion_name, changes
    for li in ul.find_all("li", recursive=False):
        label = _get_clean_text(li.span) if li.span else "General"
        sub_changes = [_get_clean_text(c) for c in li.find_all("li", recursive=False)]
        changes[label] = sub_changes

    return champion_name, changes


def _scrape_patch_rest(content: Tag, object_type: str) -> dict:
    object_start = content.find("span", id=object_type)
    object_changes = {"new": [], "changed": {}, "deleted": []}
    if not object_start:
        return object_changes
    
    object_start = object_start.find_parent("h3")
    for sibling in object_start.find_next_siblings():
        if sibling.name == "dl":
            name, changes = _scrape_patch_object(sibling)
            if changes is None:
                object_changes["new"].append(name)
            elif changes == ["del"]:
                object_changes["deleted"].append(name)
            else:
                object_changes["changed"][name] = changes
        elif sibling.name == "ul":
            continue
        else:
            break
    
    return object_changes



def _scrape_patch_object(content: Tag) -> tuple[str, list[str] | None]:
    if " - New " in content.text or " - Re-added" in content.text:
        object_name = content.text.split(" - ")[0].strip()
        return object_name, None
    
    if " - Removed" in content.text:
        object_name = _get_clean_text(content, remove=" - Removed")
        return object_name, ["del"]
    
    object_name = _get_clean_text(content)
    ul = content.find_next_sibling()
    if not ul:
        return object_name, []

    changes = [_get_clean_text(change) for change in ul.find_all("li", recursive=False)]

    return object_name, changes

    

def _scrape_hotfix(content: Tag, hotfix: datetime) -> dict[str, dict]:
    patch_changes = {
        "champions": {"changed": {}},
        "items": {"changed": {}},
        "runes": {"changed": {}},
        "summonerspells": {"changed": {}}
    }
    wiki_hotfix = datetime_to_wiki(hotfix)
    span = content.find("span", id=wiki_hotfix.replace(" ", "_"))
    hotfix_start = span.find_parent("h3") if span else None
    if not hotfix_start:
        patch_logger.error(f"[HOTFIX] [SCRAPE] [{hotfix}] Hotfix not found in wiki content")
        return patch_changes
    for sibling in hotfix_start.find_next_siblings():
        if sibling.name == "dl":
            try:
                object_type, name, object = _scrape_hotfix_all(sibling)
                patch_changes[object_type]["changed"][name] = object
            except ScrapeError as e:
                patch_logger.error(f"[HOTFIX] [SCRAPE] [{hotfix}] {e.reason}")
                continue
        elif sibling.name == "ul":
            continue
        else:
            break

    return patch_changes



def _scrape_hotfix_all(content: Tag) -> tuple[str, str, dict | list]:
    name = content.dt.find("span")
    if not name or not name.has_attr("data-param"):
        raise ScrapeError("Object type not found '{content.text}'", type="object", name="")
    
    if name.has_attr("data-champion"):
        name, value = _scrape_hotfix_champion(content)
        object_type = "champions"
    elif name.has_attr("data-item"):
        name, value = _scrape_hotfix_object(content)
        object_type = "items"
    elif name.has_attr("data-rune"):
        name, value = _scrape_hotfix_object(content)
        object_type = "runes"
    elif name.has_attr("data-spell"):
        name, value = _scrape_hotfix_object(content)
        object_type = "summonerspells"
    else:
        raise ScrapeError("Object type not found '{content.text}'", type="object", name="")

    return object_type, name, value
    
    
def _scrape_hotfix_champion(content: Tag) -> tuple[str, dict]:
    champion_name = _get_clean_text(content)
    changes = {}
    ul = content.find_next_sibling()
    if not ul:
        return champion_name, changes
    for li in ul.find_all("li", recursive=False):
        label = _get_clean_text(li.span) if li.span else "General"
        sub_changes = [_get_clean_text(c) for c in li.find_all("li")]
        changes[label] = sub_changes

    return champion_name, changes


def _scrape_hotfix_object(content: Tag) -> tuple[str, list[str]]: 
    object_name = _get_clean_text(content)
    ul = content.find_next_sibling()
    if not ul:
        return object_name, []

    changes = [_get_clean_text(change) for change in ul.find_all("li")]

    return object_name, changes



def _get_clean_text(tag: Tag, strip: str = "", remove: str = "") -> str:
    string = tag.get_text()
    removed = string.replace(remove, "")
    cleaned = unicodedata.normalize("NFKD", removed)
    stripped = cleaned.strip().strip(strip)
    return stripped