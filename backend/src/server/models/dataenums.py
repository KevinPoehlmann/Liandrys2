from abc import ABC
from aenum import MultiValueEnum
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field, validator



############### Enums ###############

#General
    
class Stat(str, MultiValueEnum):
    ABILITY_HASTE="ability haste"
    AD="ad", "attack damage", "AD", 'per 100 AD'
    AP="ap", "ability power", "AP", 'per 100 AP'
    ARMOR="armor", "total armor"
    ARMOR_PEN_P="armor penetration percent"
    ATTACKSPEED_P="attackspeed", "attack speed percent"
    CRIT_P="critical strike chance percent", 'critical strike chance'
    ENERGY="Energy", "energy"
    GOLD_P_10="gold per 10 seconds"
    HEAL_N_SHIELD_P="heal and shield power percent"
    HP="hp", "health"
    HP_P="health percent"
    HP_REG="hp_regen"
    HP_REG_P="base health regen percent", "base health regeneration percent"
    LETHALITY="lethality", "Lethality"
    LIFE_STEAL_P="life steal percent"
    MAGIC_PEN="magic penetration"
    MAGIC_PEN_P="magic penetration percent"
    MANA="mana", "Mana", " Mana", " mana"
    MANA_REG="mana_regen"
    MANA_REG_P="base mana regen percent", "base mana regeneration percent" 
    MOVESPEED="movementspeed", "move speed", "movement speed"
    MOVESPEED_P="move speed percent", "movement speed percent", "bonus movement speed percent"
    MR="mr", "magic resist", "magic resistance", "total magic resistance"
    OMNIVAMP_P="omnivamp percent"
    SLOW_RESIST_P="slow resist percent"
    SUMMONER_HASTE="summoner spell haste"
    TENACITY_P="tenacity percent"

    ARMOR_TARGET="target's armor", "of target's armor"
    BONUS_AD="bonus ad", "bonus AD", "bonus attack damage", 'per 100 bonus AD'
    BONUS_AP="bonus ap"
    BONUS_ARMOR="bonus armor"
    BONUS_ATTACKSPEED_P="bonus attackspeed", "bonus attack speed percent", 'bonus attack speed'
    BONUS_HP="bonus health", 'of his bonus health'
    BONUS_HP_P="bonus health percent"
    BONUS_MANA="bonus mana"
    BONUS_MOVESPEED="bonus movement speed"
    BONUS_MR="bonus magic resistance", 'per 100 bonus magic resistance'
    CHARGE="Charge"
    CURENT_HP_TARGET="of target's current health", "of the target's current health"
    MAX_HP="maximum health", 'of her maximum health', 'of maximum health', 'of his maximum health'
    MAX_HP_TARGET="target's maximum health", "of target's maximum health", "of the target's maximum health"
    MAX_MANA='maximum mana'
    MISSING_HP="missing health", "of missing health", 'his missing health', 'of his missing health'
    MISSING_HP_TARGET="of target's missing health", "target's missing health", "of the target's missing health"
    MISSING_MANA='of missing mana'
    UNITS="units"
    
    SECONDS="seconds"
    FLAT="Flat"
    ERROR="Error"

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


class Map(str, MultiValueEnum):
    SR="SR", "11"
    HA="HA", "12"
    NB="NB", "21"
    AR="Arena", "30"
    TFT="TFT", "22"


class Actor(Enum):
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

class Skill(str, Enum):
    Q="skill skill_q"
    W="skill skill_w"
    E="skill skill_e"
    R="skill skill_r"



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

class MinionAggro(str, Enum):
    DRAWN="Drawn"
    NOT="Not Drawn"
    NOTES="See Notes"

class CounterType(str, Enum):
    DISRUPTION="Disruption"
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

class StatusType(str, MultiValueEnum):
    AIRBORNE="Airborne"
    BERSERK="Berserk"
    BLIND="Blind"
    CRIPPLE="Cripple"
    DISARM="Disarm"
    DROWSY="Drowsy"
    GROUND="Ground", "Root"
    KINEMATICS="Kinematics"
    NEARSIGHT="Nearsight"
    REPLACE="Replace"
    SILENCE="Silence"
    SLEEP="Sleep"
    SLOW="Slow"
    STASIS="Stasis"
    STUN="Stun", "Charm", "Flee", "Polymorph"
    SUPPRESSION="Suppression"
    SUSPENSION="Suspension"
    TAUNT="Taunt"
    ERROR="Error"
    """ CHARM="Charm"
    FLEE="Flee"
    POLYMOROPH="Polymorph"
    ROOT="Root" """
    #TODO add status like poisoned

class TableTitle(str, MultiValueEnum):
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
    RANK="Rank",
    SECONDS="seconds"
    STACKS="Stacks", "stacks"
    ERROR="Error"


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

class Table(BaseModel):
    top: list[float] = [1]
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
    dmg_sub_type: DamageSubType = DamageSubType.PHYSIC
    hp_scaling: HpScaling = HpScaling.FLAT
    vamp: float = 0


class HealProperties(EffectProperties):
    scaling: str
    hp_scaling: HpScaling = HpScaling.FLAT


class ShieldProperties(EffectProperties):
    scaling: str
    duration: float
    dmg_sub_type: DamageSubType = DamageSubType.TRUE
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
    dmg_sub_type: DamageSubType = DamageSubType.PHYSIC
    hp_scaling: HpScaling = HpScaling.FLAT
    vamp: float = 0


class ProcessedHealProperties(EffectProperties):
    value: float
    hp_scaling: HpScaling = HpScaling.FLAT


class ProcessedShieldProperties(EffectProperties):
    value: float
    duration: float
    dmg_sub_type: DamageSubType = DamageSubType.TRUE
    hp_scaling: HpScaling = HpScaling.FLAT


class ProcessedStatusProperties(EffectProperties):
    type_: StatusType
    duration: float
    strength: float = 0.0



############### Dataclasses ###############

@dataclass
class ChampionSideBox():
    last_changed: str
    range_type: RangeType



@dataclass
class AttackspeedStats():
    attackspeed_ratio: float
    attack_windup: float = 0.0
    windup_modifier: float = 1.0
    missile_speed: int = 0



@dataclass
class AbilityDetails():
    damage_type: DamageType = None
    damage_sub_type: list[DamageSubType] = field(default_factory=list)
    minion_aggro: MinionAggro = None
    counters: list[Counter] = field(default_factory=list)

    
@dataclass
class AbilityBaseStats():
    cast_time: float = 0
    cooldown: Table = None
    costs: AbilityCosts = None
    ability_stats: list[AbilityStat] = field(default_factory=list)





@dataclass
class Action():
    actor: Actor
    target: Actor
    action_type: ActionType

### Status Queue ###


#Queue


@dataclass 
class QueueComponent():
    source: ActionType
    actor: Actor
    target: Actor
    type_: EffectType
    props: EffectProperties = None



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
    props: EffectProperties = None




@dataclass
class ActionEffect():
    time: float
    effect_comps: list[EffectComp] = field(default_factory=list)


@dataclass
class Damage():
    pass