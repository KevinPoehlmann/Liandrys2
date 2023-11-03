from dataclasses import dataclass, field
from enum import Enum
from aenum import MultiValueEnum
from pydantic import BaseModel



############### Enums ###############

#General
    
class Stat(str, MultiValueEnum):
    ABILITY_HASTE="ability haste"
    AP="ability power", "AP"
    ARMOR="armor"
    ARMOR_PEN_P="armor penetration percent"
    AD="attack damage", "AD"
    ATTACKSPEED_P="attack speed percent"
    MANA_REG_P="base mana regen percent", "base mana regeneration percent"
    HP_REG_P="base health regen percent", "base health regeneration percent"
    CRIT_P="critical strike chance percent"
    GOLD_P_10="gold per 10 seconds"
    HP="health"
    HEAL_N_SHIELD_P="heal and shield power percent"
    LETHALITY="lethality", "Lethality"
    LIFE_STEAL_P="life steal percent"
    MAGIC_PEN="magic penetration"
    MAGIC_PEN_P="magic penetration percent"
    MR="magic resist", "magic resistance"
    MANA="mana", "Mana", " Mana", " mana"
    MOVESPEED="move speed", "movement speed"
    MOVESPEED_P="move speed percent", "movement speed percent", "bonus movement speed percent"
    OMNIVAMP_P="omnivamp percent"
    SLOW_RESIST_P="slow resist percent"
    SUMMONER_HASTE="summoner spell haste"
    TENACITY_P="tenacity percent"

    ARMOR_TARGET="target's armor", "of target's armor"
    BONUS_AD="bonus AD", "bonus attack damage"
    BONUS_ARMOR="bonus armor"
    BONUS_ATTACKSPEED_P="bonus attack speed percent"
    BONUS_MR="bonus magic resistance"
    BONUS_HP="bonus health", 'of his bonus health'
    BONUS_HP_P="bonus health percent"
    BONUS_MOVESPEED="bonus movement speed"
    CUURENT_HP_TARGET="of target's current health", "of the target's current health"
    ENERGY="Energy"
    MAX_HP="maximum health", 'of her maximum health', 'of maximum health', 'of his maximum health'
    MAX_HP_TARGET="target's maximum health", "of target's maximum health", "of the target's maximum health"
    MAX_MANA='maximum mana'
    MISSING_HP="missing health", "of missing health", 'his missing health', 'of his missing health'
    MISSING_HP_TARGET="of target's missing health"
    MISSING_MANA='of missing mana'
    
    ERROR="Error"


#Champions

class RangeType(str, Enum):
    MELEE="Melee"
    RANGED="Ranged"

class ResourceType(str, MultiValueEnum):
    MANA="Mana"
    BLOOD_WELL="Blood Well"
    COURAGE="Courage"
    CRIMSON_RUSH="Crimson Rush"
    ENERGY="Energy"
    FEROCITY="Ferocity"
    FLOW="Flow"
    FURY="Fury"
    GRIT="Grit"
    HEAT="Heat"
    RAGE="Rage"
    SHIELD="Shield"
    NONE="None", ""


#Items

class ItemClass(str, MultiValueEnum):
    ADV_CONSUMABLE="advanced consumable item"
    BASIC="Basic", "basic item"
    BOOTS="boots item"
    CONSUMABLE="consumable item"
    DISTRIBUTED="distributed item"
    EPIC="epic item"
    LEGENDARY="legendary item"
    MYTHIC="mythic item"
    NONE=""
    STARTER="starter item"
    TOWER_MINION="tower and minion item"
    ERROR="Error"


#Ability details

class DamageType(str, Enum):
    AOE="Area damage"
    AOE_DOT="AOE DOT damage"
    BASIC="Basic damage"
    DEFAULT="Default damage"
    DOT="DOT damage"
    NON="Non-Damaging"
    NOTES="See Notes"
    PET="Pet damage"
    PROC="Proc damage"
    SPELL="Spell damage"

class DamageSubType(str, MultiValueEnum):
    PHYSIC="Physical", "Physical damage", " Physical damage", " Physical"
    MAGIC="Magic", "Magic damage", " Magic", ' Magic damage'
    TRUE="True", "True damage", " True", " True damage"


class CounterType(str, Enum):
    GROUNDED="Grounded"
    KNOCKDOWN="Knockdown"
    PARRIES="Parries"
    PROJECTILE="Projectile"
    SPELL_SHIELD="Spell shield"

class CounterEffect(str, MultiValueEnum):
    BLOCKED ="Blocked"
    BYPASS="Bypass"
    DISABLED="Disabled"
    INTERRUPTED="Interrupted"
    NA="N/A", "Missing"
    NOT_BLOCKED="Not Blocked"
    NOT_DISABLED="Not Disabled"
    NOT_INTERRUPTED="Not Interrupted"
    SEE_NOTES="See Notes"


#Abilities

class AbilityStatKey(str, MultiValueEnum):
    ANGLE="ANGLE"
    BARRAGE_COOLDOWN="Barrage Cooldown"
    CAST_TIME="CAST TIME"
    CHARGES="charges"
    COLLSION_RADIUS="COLLISION RADIUS"
    COOLDOWN="COOLDOWN", "cool down", "cooldown"
    COST="COST"
    DETECTION_RADIUS="Detection Radius"
    DISABLE_TIME="Disable Time"
    EFFECT_RADIUS="EFFECT RADIUS"
    IMPASSABLE_PERIMETER="Impassable perimeter"
    INNER_RADIUS="INNER RADIUS"
    LEASH_RANGE="Leash Range"
    LEVEL="level"
    ON_TARGET_COOLDOWN="On-Target Cooldown"
    ON_TERRAIN_COOLDOWN="On-Terrain Cooldown"
    PER_DIRECTION_COOLDOWN="Per-Direction Cooldown"
    PER_LEG_COOLDOWN="Per-Leg Cooldown"
    PILLAR_RADIUS="Pillar radius"
    RANGE="RANGE", "range"
    RECHARGE="RECHARGE"
    SIDE_LENGTH="Side length"
    SIGHT_REDUCTION="Sight Reduction"
    SIZE_RADIUS="Size Radius"
    SPEED="SPEED"
    STATIC_COOLDOWN="STATIC COOLDOWN"
    STEALTH="stealth"
    TARGET_IMMUNITY="TARGET IMMUNITY"
    TARGET_RANGE="TARGET RANGE"
    TETHER_RADIS="TETHER RADIUS"
    WIDTH="WIDTH"
    ERROR="Error"


class ActiveType(str, Enum):
    ACTIVE="Active"
    CONSUME="Consume"


#Effects

class ConditionType(str, Enum):
    HIT="hit"
    RANGE="range"
    EFFECT="effect"

class StatusType(str, Enum):
    AIRBORNE="Airborne"
    BERSERK="Berserk"
    BLIND="Blind"
    CHARM="Charm"
    CRIPPLE="Cripple"
    DISARM="Disarm"
    DROWSY="Drowsy"
    FLEE="Flee"
    GROUND="Ground"
    KINEMATICS="Kinematics"
    NEARSIGHT="Nearsight"
    POLYMOROPH="Polymorph"
    ROOT="Root"
    SILENCE="Silence"
    SLEEP="Sleep"
    SLOW="Slow"
    STASIS="Stasis"
    STUN="Stun"
    SUPPRESSION="Suppression"
    SUSPENSION="Suspension"
    TAUNT="Taunt"
    #TODO add status like poisoned

class TableTitle(str, MultiValueEnum):
    CHANNEL_TIME="channel time"
    CHARGE_TIME="CHARGE TIME", 'seconds charged', 'charge time'
    CHIMES="number of Chimes"
    CONST="Constant"
    CRIT_CHANCE='critical strike chance'
    DISTANCE="distance traveled"
    DURATION="duration"
    FURY="Fury"
    LEVEL="level", "Ornn's level"
    MARKS="marks"
    MISSING_HO="missing health"
    MISSING_HP_T="target's missing health"
    RANK="Rank",
    SECONDS="seconds"
    STACKS="Stacks", "stacks"
    ERROR="Error"



############### BaseModels ###############

class Table(BaseModel):
    top: list[float]
    bot: list[float]
    title: TableTitle = TableTitle.RANK


class Counter(BaseModel):
    type_: CounterType
    effect: CounterEffect


class AbilityCosts(BaseModel):
    values: Table = None
    unit: Stat = None


class AbilityStat(BaseModel):
    key: AbilityStatKey
    values: str


class ItemStat(BaseModel):
    stat: Stat
    value: float


class Mythic(BaseModel):
    stat: Stat
    value: float





############### Dataclasses ###############

@dataclass
class ChampionSideBox():
    """Class for storing side box stats from a champion"""
    last_changed: str
    range_type: RangeType



@dataclass
class AttackspeedStats():
    """Class for champion's stats for its attack windup, windup modificator and attackspeed ratio."""
    attackspeed_ratio: float
    attack_windup: float = 0.0
    windup_modifier: float = 1.0
    missile_speed: int = 0


@dataclass
class AbilityDetails():
    """"""
    damage_type: DamageType = None
    damage_sub_type: list[DamageSubType] = field(default_factory=list)
    counters: list[Counter] = field(default_factory=list)

    
@dataclass
class AbilityBaseStats():
    """"""
    cast_time: float = 0
    cooldown: Table = None
    costs: AbilityCosts = None
    ability_stats: list[AbilityStat] = field(default_factory=list)

