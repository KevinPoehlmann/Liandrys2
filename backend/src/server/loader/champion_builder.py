"""Builds the loader's part of a champion from its raw data: named values and tooltips per ability."""
import re
from dataclasses import dataclass

from src.server.loader.cdragon import SpellValues, bin_field, spell_values
from src.server.loader.champion_source import loc_keys
from src.server.models.ability import Ability, ChampionAbility
from src.server.models.champion import NewChampion, RawChampion, WikiTemplate
from src.server.models.enums import AdaptiveType, RangeType, ResourceType
from src.server.models.image import Image
from src.server.models.json_validation import ChampionJson
from src.server.models.passive import ChampionPassive, Passive


SLOTS = ("q", "w", "e", "r")
WIKI_SLOTS = {"Q": "q", "W": "w", "E": "e", "R": "r", "I": "passive"}  # the wiki calls the passive "I" (innate)
REDIRECT = re.compile(r"#REDIRECT \[\[(.+?)\]\]")


def build_champion(raw: RawChampion, entry: ChampionJson) -> NewChampion:
    """A newly loaded champion: stats and named values from CDragon, list data (key, ranks, resource, images) from Data Dragon."""
    max_ranks = {slot: spell.maxrank for slot, spell in zip(SLOTS, entry.spells)}
    spells = loaded_spells(raw, max_ranks)
    abilities = {slot: _new_ability(spells[slot], ddragon_spell.name, ddragon_spell.maxrank, ddragon_spell.image)
                 for slot, ddragon_spell in zip(SLOTS, entry.spells)}
    champion = NewChampion(
        key=entry.key, name=entry.name, champion_id=raw.champion_id, patch=raw.patch, hotfix=raw.hotfix,
        resource_type=ResourceType.from_str(entry.partype), image=entry.image,
        passive=ChampionPassive(name=spells["passive"].name or entry.passive.name, image=entry.passive.image),
        **abilities, **champion_stats(raw.cdragon),
    )
    apply_loader_part(champion, spells)
    return champion


def _new_ability(spell: "LoadedSpell", ddragon_name: str, max_rank: int, image: Image) -> ChampionAbility:
    ability = ChampionAbility(name=spell.name or ddragon_name, maxrank=max_rank, image=image)
    initial_structure(ability)
    return ability


@dataclass
class LoadedSpell:
    script_name: str
    name: str
    tooltip: str
    values: SpellValues
    wiki: WikiTemplate | None


def loaded_spells(raw: RawChampion, max_ranks: dict[str, int]) -> dict[str, LoadedSpell]:
    """Q, W, E, R and the passive, found through the champion's own record (the passive has no ranks)."""
    record = _character_record(raw.cdragon)
    paths = dict(zip(SLOTS, record["spells"])) | {"passive": record["mCharacterPassiveSpell"]}
    strings = {key.lower(): text for key, text in raw.strings.items()}
    templates = _wiki_by_slot(raw.wiki)
    return {slot: _loaded_spell(raw.cdragon[path], max_ranks.get(slot, 0), strings, templates.get(slot))
            for slot, path in paths.items()}


def _loaded_spell(record: dict, max_rank: int, strings: dict[str, str], wiki: WikiTemplate | None) -> LoadedSpell:
    keys = loc_keys(record)
    return LoadedSpell(
        script_name=record["mScriptName"],
        name=strings.get(keys.get("keyName", "").lower(), ""),
        tooltip=strings.get(keys.get("keyTooltip", "").lower(), ""),
        values=spell_values(record["mSpell"], max_rank),
        wiki=wiki,
    )


def _wiki_by_slot(templates: dict[str, WikiTemplate]) -> dict[str, WikiTemplate]:
    # "Template:Data Veigar/Q" redirects to "Template:Data Veigar/Baleful Strike".
    by_slot = {}
    for title, template in templates.items():
        slot = WIKI_SLOTS.get(title.rsplit("/", 1)[-1])
        target = REDIRECT.match(template.text)
        if slot and target and target.group(1) in templates:
            by_slot[slot] = templates[target.group(1)]
    return by_slot


def champion_stats(cdragon: dict) -> dict:
    """The champion's base stats in our units. Riot leaves out fields that have their default value."""
    record = _character_record(cdragon)
    resource = record.get("primaryAbilityResource", {})
    stat = lambda source, name, default=0.0: bin_field(source, name, {}).get("baseValue", default)
    attack_speed = stat(record, "attackSpeedModifiable")
    return {
        "hp": stat(record, "baseHPModifiable"), "hp_per_lvl": stat(record, "hpPerLevelModifiable"),
        "ad": stat(record, "baseDamageModifiable"), "ad_per_lvl": stat(record, "damagePerLevelModifiable"),
        "mana": stat(resource, "arBaseModifiable"), "mana_per_lvl": stat(resource, "arPerLevelModifiable"),
        "armor": stat(record, "baseArmorModifiable"), "armor_per_lvl": stat(record, "armorPerLevelModifiable"),
        "mr": stat(record, "baseMR"), "mr_per_lvl": stat(record, "mrPerLevel"),
        "movementspeed": stat(record, "baseMoveSpeedModifiable"), "attackrange": stat(record, "attackRangeModifiable"),
        # Per second like Riot (the wiki and Data Dragon show per 5 seconds).
        "hp_regen": stat(record, "baseStaticHPRegenModifiable"), "hp_regen_per_lvl": stat(record, "hpRegenPerLevelModifiable"),
        "mana_regen": stat(resource, "arBaseStaticRegenModifiable"), "mana_regen_per_lvl": stat(resource, "arRegenPerLevelModifiable"),
        "attackspeed": attack_speed, "attackspeed_ratio": stat(record, "attackSpeedRatioModifiable", attack_speed),
        "attackspeed_per_lvl": stat(record, "attackSpeedPerLevelModifiable") / 100,
        "attack_windup": _attack_windup(record.get("basicAttack", {})),
        "windup_modifier": record.get("basicAttack", {}).get("mAttackDelayCastOffsetPercentAttackSpeedRatio", 1.0),
        "missile_speed": _missile_speed(cdragon, record),
        "range_type": RangeType(record.get("purchaseIdentities", ["Melee"])[0]),  # Nidalee lists both, her base form first
        "adaptive_type": AdaptiveType.MAGIC if record.get("mAdaptiveForceToAbilityPowerWeight") else AdaptiveType.PHYSICAL,
    }


def _attack_windup(attack: dict) -> float:
    # Riot's base is 30 % of the attack time, shifted per champion; a few give cast and total time instead (Vladimir).
    if "mAttackCastTime" in attack:
        return attack["mAttackCastTime"] / attack["mAttackTotalTime"]
    if "mAttackDelayCastOffsetPercent" in attack:
        return 0.3 + attack["mAttackDelayCastOffsetPercent"]
    raise ValueError("The basic attack has no windup (neither a cast offset nor cast and total time)")


def _missile_speed(cdragon: dict, record: dict) -> float:
    # The spell's `missileSpeed` field is outdated; the missile's movement component holds the real speed.
    attack = next((r for r in cdragon.values() if isinstance(r, dict)
                   and r.get("mScriptName") == f"{record['mCharacterName']}BasicAttack"), {})
    return attack.get("mSpell", {}).get("mMissileSpec", {}).get("movementComponent", {}).get("mSpeed", 0.0)


def _character_record(cdragon: dict) -> dict:
    return next(r for r in cdragon.values() if isinstance(r, dict) and r.get("__type") == "CharacterRecord")


def apply_loader_part(champion: NewChampion, spells: dict[str, LoadedSpell]) -> None:
    """Overwrites what the loader owns; rules, buffs, stages and formula fields stay as they are."""
    for slot, spell in spells.items():
        container: Ability | Passive = getattr(champion, slot)
        container.values = spell.values.values
        container.tooltip = spell.tooltip


def initial_structure(ability: Ability) -> None:
    """A newly loaded ability starts with the defaults that fit almost every ability; afterwards they are hand-owned."""
    ability.cost = "mana"
    ability.cooldown = "cooldownTime"
