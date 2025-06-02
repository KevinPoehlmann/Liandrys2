from abc import ABC
from aenum import MultiValueEnum
from dataclasses import dataclass, field
from enum import Enum
from typing import cast
from pydantic import BaseModel, Field, validator



############### Enums ###############

#General
    
class Stat(str, Enum):
    ABILITY_HASTE = "ability haste"
    AD = "ad"
    AP = "ap"
    ARMOR = "armor"
    ARMOR_PEN_P = "armor penetration percent"
    ATTACKSPEED_P = "attackspeed"
    CRIT_P = "critical strike chance percent"
    ENERGY = "energy"
    GOLD_P_10 = "gold per 10 seconds"
    HEAL_N_SHIELD_P = "heal and shield power percent"
    HP = "hp"
    HP_P = "health percent"
    HP_REG = "hp_regen"
    HP_REG_P = "base health regen percent"
    LETHALITY = "lethality"
    LIFE_STEAL_P = "life steal percent"
    MAGIC_PEN = "magic penetration"
    MAGIC_PEN_P = "magic penetration percent"
    MANA = "mana"
    MANA_REG = "mana_regen"
    MANA_REG_P = "base mana regen percent"
    MOVESPEED = "movementspeed"
    MOVESPEED_P = "move speed percent"
    MR = "mr"
    OMNIVAMP_P = "omnivamp percent"
    SLOW_RESIST_P = "slow resist percent"
    SUMMONER_HASTE = "summoner spell haste"
    TENACITY_P = "tenacity percent"
    ARMOR_TARGET = "target's armor"
    BONUS_AD = "bonus ad"
    BONUS_AP = "bonus ap"
    BONUS_ARMOR = "bonus armor"
    BONUS_ATTACKSPEED_P = "bonus attackspeed"
    BONUS_HP = "bonus health"
    BONUS_HP_P = "bonus health percent"
    BONUS_MANA = "bonus mana"
    BONUS_MOVESPEED = "bonus movement speed"
    BONUS_MR = "bonus magic resistance"
    CHARGE = "Charge"
    CURENT_HP_TARGET = "of target's current health"
    MAX_HP = "maximum health"
    MAX_HP_TARGET = "target's maximum health"
    MAX_MANA = "maximum mana"
    MISSING_HP = "missing health"
    MISSING_HP_TARGET = "target's missing health"
    MISSING_MANA = "of missing mana"
    UNITS = "units"
    SECONDS = "seconds"
    FLAT = "Flat"
    ERROR = "Error"

    @classmethod
    def from_str(cls, value: str) -> "Stat":
        alias_map = {
            # All alias values mapping to enum members
            "attack damage": cls.AD, "AD": cls.AD, "per 100 AD": cls.AD,
            "ability power": cls.AP, "AP": cls.AP, "per 100 AP": cls.AP,
            "total armor": cls.ARMOR,
            "attack speed percent": cls.ATTACKSPEED_P,
            "critical strike chance": cls.CRIT_P,
            "Energy": cls.ENERGY,
            "base health regeneration percent": cls.HP_REG_P,
            "Lethality": cls.LETHALITY,
            "Mana": cls.MANA, " Mana": cls.MANA, " mana": cls.MANA,
            "base mana regeneration percent": cls.MANA_REG_P,
            "move speed": cls.MOVESPEED, "movement speed": cls.MOVESPEED,
            "movement speed percent": cls.MOVESPEED_P, "bonus movement speed percent": cls.MOVESPEED_P,
            "magic resist": cls.MR, "magic resistance": cls.MR, "total magic resistance": cls.MR,
            "bonus AD": cls.BONUS_AD, "bonus attack damage": cls.BONUS_AD, "per 100 bonus AD": cls.BONUS_AD,
            "bonus AP": cls.BONUS_AP,
            "bonus attack speed percent": cls.BONUS_ATTACKSPEED_P, "bonus attack speed": cls.BONUS_ATTACKSPEED_P,
            "of his bonus health": cls.BONUS_HP,
            "per 100 bonus magic resistance": cls.BONUS_MR,
            "of target's current health": cls.CURENT_HP_TARGET, "of the target's current health": cls.CURENT_HP_TARGET,
            "of her maximum health": cls.MAX_HP, "of maximum health": cls.MAX_HP, "of his maximum health": cls.MAX_HP,
            "of target's maximum health": cls.MAX_HP_TARGET, "of the target's maximum health": cls.MAX_HP_TARGET,
            "of missing health": cls.MISSING_HP, "his missing health": cls.MISSING_HP, "of his missing health": cls.MISSING_HP,
            "of target's missing health": cls.MISSING_HP_TARGET, "of the target's missing health": cls.MISSING_HP_TARGET,
            "health": cls.HP,
            "base health regen percent": cls.HP_REG_P,
            "gold per 10": cls.GOLD_P_10,  # if used that way
            "bonus attack speed": cls.BONUS_ATTACKSPEED_P,
            "bonus movement speed": cls.BONUS_MOVESPEED,
            "bonus armor": cls.BONUS_ARMOR,
            "bonus mana": cls.BONUS_MANA,
            "bonus health percent": cls.BONUS_HP_P,
            "bonus health": cls.BONUS_HP,
            "omnivamp percent": cls.OMNIVAMP_P,
            "slow resist percent": cls.SLOW_RESIST_P,
            "summoner spell haste": cls.SUMMONER_HASTE,
            "tenacity percent": cls.TENACITY_P,
            "units": cls.UNITS,
            "seconds": cls.SECONDS,
            "flat": cls.FLAT,
        }
        try:
            return cls(value)
        except ValueError:
            lowered = value.strip().lower()
            for alias, member in alias_map.items():
                if lowered == alias.lower():
                    return member
            raise ValueError(f"{value!r} is not a valid alias for {cls.__name__}")

"""     CHANNEL_TIME="channel time"
    CHARGE_TIME="CHARGE TIME", 'seconds charged', 'charge time'
    CHIMES="number of Chimes"
    CONST="Constant"
    DISTANCE="distance traveled"
    DURATION="duration"
    FURY="Fury"
    LEVEL="level", "Ornn's level"
    MARKS="marks"
    RANK="Rank",
    SECONDS="seconds"
    STACKS="Stacks", "stacks" """




class ActionType(str, Enum):
    AA="aa"
    Q="q"
    W="w"
    E="e"
    R="r"
    PASSIVE="passive"
    S1="s1"
    S2="s2"
    I1="i1"
    I2="i2"
    I3="i3"
    I4="i4"
    I5="i5"
    I6="i6"


class Map(str, MultiValueEnum):
    SR="SR", "11"
    HA="HA", "12"
    NB="NB", "21"
    AR="Arena", "30"
    TFT="TFT", "22"


class Actor(str, Enum):
    BLUE = "blue"
    RED = "red"

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

""" class Skill(str, Enum):
    Q="skill skill_q"
    W="skill skill_w"
    E="skill skill_e"
    R="skill skill_r" """



#Items

class ItemClass(str, MultiValueEnum):
    ADV_CONSUMABLE="advanced consumable item"
    BASIC="Basic", "basic item"
    BOOTS="boots item"
    CONSUMABLE="consumable item"
    DISTRIBUTED="distributed item"
    EPIC="epic item"
    LEGENDARY="legendary item"
    MASTERWORK="masterwork item"
    NONE="None", ""
    STARTER="starter item"
    TRINKET="trinket item"
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
    ADAPTIVE="Adaptive"

""" class MinionAggro(str, Enum):
    DRAWN="Drawn"
    NOT="Not Drawn"
    NOTES="See Notes" """

""" class CounterType(str, Enum):
    DISRUPTION="Disruption"
    GROUNDED="Grounded"
    KNOCKDOWN="Knockdown"
    PARRIES="Parries"
    PROJECTILE="Projectile"
    SPELL_SHIELD="Spell shield" """

""" class CounterEffect(str, MultiValueEnum):
    BLOCKED ="Blocked"
    BYPASS="Bypass"
    DISABLED="Disabled"
    INTERRUPTED="Interrupted"
    NA="N/A", "Missing"
    NOT_BLOCKED="Not Blocked"
    NOT_DISABLED="Not Disabled"
    NOT_INTERRUPTED="Not Interrupted"
    SEE_NOTES="See Notes" """


#Abilities

""" class AbilityStatKey(str, MultiValueEnum):
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
    ERROR="Error" """


class AbilityStat(str, Enum):
    COOLDOWN = "cooldown"
    COST = "cost"
    CAST_TIME = "cast_time"
    SPEED = "speed"
    RECHARGE = "recharge"
    DURATION = "duration"



class ActiveType(str, Enum):
    ACTIVE="Active"
    CONSUME="Consume"


#Effects

class EffectType(str, Enum):
    DAMAGE="Damage"
    HEAL="Heal"
    SHIELD="Shield"
    SHADOW="Shadow"
    STATUS="Status"

class ConditionType(str, Enum):
    HIT="hit"
    RANGE="range"
    EFFECT="effect"

class StatusType(str, Enum):
    AIRBORNE = "Airborne"
    BERSERK = "Berserk"
    BLIND = "Blind"
    CRIPPLE = "Cripple"
    DISARM = "Disarm"
    DROWSY = "Drowsy"
    GROUND = "Ground"
    KINEMATICS = "Kinematics"
    NEARSIGHT = "Nearsight"
    REPLACE = "Replace"
    SILENCE = "Silence"
    SLEEP = "Sleep"
    SLOW = "Slow"
    STASIS = "Stasis"
    STUN = "Stun"
    SUPPRESSION = "Suppression"
    SUSPENSION = "Suspension"
    TAUNT = "Taunt"
    ERROR = "Error"

    @classmethod
    def from_str(cls, value: str) -> "StatusType":
        alias_map = {
            "Root": cls.GROUND,
            "Charm": cls.STUN,
            "Flee": cls.STUN,
            "Polymorph": cls.STUN,
        }
        try:
            return cls(value)
        except ValueError:
            lowered = value.strip().lower()
            for alias, member in alias_map.items():
                if lowered == alias.lower():
                    return member
            raise ValueError(f"{value!r} is not a valid alias for {cls.__name__}")
    """ CHARM="Charm"
    FLEE="Flee"
    POLYMOROPH="Polymorph"
    ROOT="Root" """

""" class TableTitle(str, MultiValueEnum):
    CHANNEL_TIME="channel time"
    CHARGE_TIME="CHARGE TIME", 'seconds charged', 'charge time'
    CHIMES="number of Chimes"
    CONST="Constant"
    CRIT_CHANCE='critical strike chance'
    DISTANCE="distance traveled"
    DURATION="duration"
    FLAT="Flat"
    FURY="Fury"
    LEVEL="level", "Ornn's level"
    MARKS="marks"
    MISSING_HP="missing health"
    MISSING_HP_T="target's missing health"
    RANK="Rank"
    SECONDS="seconds"
    STACKS="Stacks", "stacks"
    ERROR="Error" """


class HpScaling(str, Enum):
    FLAT="flat"
    MAX_HP="max health"
    MISSING_HP="missing health"
    CURRENT_HP="current health"


class Buff(str, Enum):
    CAST = "Cast"
    HIT = "Hit"
    GET_HIT = "Get Hit"
    STATS = "Stats"  

class BuffActionType(str, Enum):
    STACK="Stack"
    EFFECT="Effect"

class Comparison(str, Enum):
    GT="Greater than"
    LT="Less than"
    EQ="Equal"


############### BaseModels ###############

""" class Table(BaseModel):
    top: list[float] = [1]
    bot: list[float]
    title: TableTitle = cast(TableTitle, TableTitle.RANK) """


""" class Counter(BaseModel):
    type_: CounterType
    effect: CounterEffect """


""" class AbilityCosts(BaseModel):
    values: Table | None = None
    unit: Stat | None = None """


""" class AbilityStat(BaseModel):
    key: AbilityStatKey
    values: str """


class ItemStat(BaseModel):
    stat: Stat
    value: float


class Mythic(BaseModel):
    stat: Stat
    value: float


class Combo(BaseModel):
    pass


class Condition(BaseModel):
    key: Stat | ActionType
    comparison: Comparison
    value: float




class EffectProperties(BaseModel):
    pass


class DamageProperties(EffectProperties):
    scaling: str
    dmg_type: DamageType = DamageType.DEFAULT
    dmg_sub_type: DamageSubType = cast(DamageSubType, DamageSubType.PHYSIC)
    hp_scaling: HpScaling = HpScaling.FLAT
    vamp: float = 0


class HealProperties(EffectProperties):
    scaling: str
    hp_scaling: HpScaling = HpScaling.FLAT


class ShieldProperties(EffectProperties):
    scaling: str
    duration: float
    dmg_sub_type: DamageSubType = cast(DamageSubType, DamageSubType.TRUE)
    hp_scaling: HpScaling = HpScaling.FLAT


class StatusProperties(EffectProperties):
    type_: StatusType
    duration: float
    strength: float = 0.0


class ProcessedDamageProperties(EffectProperties):
    value: float
    flat_pen: float
    percent_pen: float
    dmg_type: DamageType
    dmg_sub_type: DamageSubType = cast(DamageSubType, DamageSubType.PHYSIC)
    hp_scaling: HpScaling = HpScaling.FLAT
    vamp: float = 0


class ProcessedHealProperties(EffectProperties):
    value: float
    hp_scaling: HpScaling = HpScaling.FLAT


class ProcessedShieldProperties(EffectProperties):
    value: float
    duration: float
    dmg_sub_type: DamageSubType = cast(DamageSubType, DamageSubType.TRUE)
    hp_scaling: HpScaling = HpScaling.FLAT


class ProcessedStatusProperties(EffectProperties):
    type_: StatusType
    duration: float
    strength: float = 0.0



############### Dataclasses ###############

""" @dataclass
class ChampionSideBox():
    last_changed: str
    range_type: RangeType """



@dataclass
class AttackspeedStats():
    attackspeed_ratio: float
    attack_windup: float = 0.0
    windup_modifier: float = 1.0
    missile_speed: int = 0



""" @dataclass
class AbilityDetails():
    damage_type: DamageType | None = None
    damage_sub_type: list[DamageSubType] = field(default_factory=list)
    minion_aggro: MinionAggro | None = None
    counters: list[Counter] = field(default_factory=list) """

    
""" @dataclass
class AbilityBaseStats():
    cast_time: float = 0
    cooldown: Table | None = None
    costs: AbilityCosts | None = None
    ability_stats: list[AbilityStat] = field(default_factory=list) """



### Status Queue ###


#Queue


@dataclass 
class QueueComponent():
    source: ActionType
    actor: Actor
    target: Actor
    type_: EffectType
    props: EffectProperties | None = None



#Status

@dataclass
class EffectComp():
    source: ActionType
    target: Actor
    type_: EffectType
    duration: float = 0.0
    interval: float = 0.0
    delay: float = 0.0
    speed: int = 0
    props: EffectProperties | None = None




@dataclass
class ActionEffect():
    time: float
    effect_comps: list[EffectComp] = field(default_factory=list)


""" @dataclass
class Damage():
    pass """