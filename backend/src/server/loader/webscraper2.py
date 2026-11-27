import locale
import logging
import unicodedata

from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass
from src.server.loader.helper import (
    wiki_to_riot_patch,
    parse_formula_from_table,
    parse_formula_from_string,
)
from src.server.loader.patchexceptions import ScrapeError
from src.server.models.ability import ChampionAbility, Ability
from src.server.models.champion import NewChampion
from src.server.models.enums import ResourceType, RangeType
from src.server.models.json_validation import ChampionJson, SpellJson, PassiveJson
from src.server.models.passive import ChampionPassive


patch_logger = logging.getLogger("liandrys.patch")
debug_logger = logging.getLogger("liandrys.debug")


@dataclass
class AttackspeedStats():
    attackspeed_ratio: float
    attack_windup: float = 0.0
    windup_modifier: float = 1.0
    missile_speed: int = 0


def scrape_champion(champion_json: ChampionJson, wiki_html: str, patch: str) -> NewChampion | None:
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
        image=passive_json.image,
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


    ability = ChampionAbility(
        name=spell_json.name,
        description=spell_json.description,
        cost=cost,
        cooldown=cooldown,
        recharge=recharge,
        raw_stats=stats,
        image=spell_json.image,
        maxrank=spell_json.maxrank,
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


def _get_clean_text(tag: Tag, strip: str = "", remove: str = "") -> str:
    string = tag.get_text()
    removed = string.replace(remove, "")
    cleaned = unicodedata.normalize("NFKD", removed)
    stripped = cleaned.strip().strip(strip)
    return stripped