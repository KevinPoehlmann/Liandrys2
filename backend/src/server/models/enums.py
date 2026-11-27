import math
import re
from enum import Enum
from typing import ClassVar



############### Constants ###############

TICK_SECONDS = 0.033  # the server ticks every 33 ms
TICKRATE = 1 / TICK_SECONDS  # about 30.3 ticks per second


def to_ticks(seconds: float) -> int:
    # Anything ending inside a tick happens on the next whole tick.
    # Rounding first removes float noise, e.g. 0.264 / 0.033 = 8.000000000000002.
    return math.ceil(round(seconds / TICK_SECONDS, 6))


############### Enums ###############

#General
    
class Stat(str, Enum):
    ABILITY_HASTE = "ability haste"
    AD = "ad"
    AF = "adaptive force"
    AP = "ap"
    ARMOR = "armor"
    ARMOR_PEN_P = "armor penetration percent"
    ATTACK_RANGE = "attackrange"  # the champion field's name, so get_base_stat finds it
    ATTACKSPEED_P = "attackspeed"
    CRIT_P = "critical strike chance percent"
    CRIT_DAMAGE = "crit_damage"
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
    Q_COOLDOWN_REDUCTION = "q cooldown reduction"
    W_COOLDOWN_REDUCTION = "w cooldown reduction"
    E_COOLDOWN_REDUCTION = "e cooldown reduction"
    R_COOLDOWN_REDUCTION = "r cooldown reduction"
    DAMAGE_TAKEN_P = "damage taken percent"
    BONUS_ATTACKSPEED_P = "bonus attackspeed"  # includes the attack speed growth per level


class ActionType(str, Enum):
    BA="ba"  # basic attack
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
    # Extra champion abilities (Nidalee's cougar form) in the order of Champion.extra_abilities; a buff maps Q/W/E/R to them.
    X1="x1"
    X2="x2"
    X3="x3"
    X4="x4"
    X5="x5"
    X6="x6"
    X7="x7"
    X8="x8"
    X9="x9"
    # Runes and stat shards have no actions; their slots only name the container for formulas, buffs and origins.
    RUNE1="rune1"
    RUNE2="rune2"
    RUNE3="rune3"
    RUNE4="rune4"
    RUNE5="rune5"
    RUNE6="rune6"
    RUNE7="rune7"
    RUNE8="rune8"
    RUNE9="rune9"


class Map(str, Enum):
    SR="SR"
    HA="HA"
    NB="NB"
    AR="Arena"
    TFT="TFT"
    BR="Brawl"
    SW="Swarm"
    SP="Swiftplay"



class Actor(str):
    """A unit in the simulation: the team first, then the path to the unit.

    'blue' and 'red' are the champions, pets hang below their owner: 'blue.tibbers', 'blue.ghoul#2'.
    """
    BLUE: ClassVar["Actor"]
    RED: ClassVar["Actor"]
    PATTERN: ClassVar[re.Pattern] = re.compile(r"(blue|red)(\.[a-z][a-z0-9_]*(#\d+)?)*")

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value) -> "Actor":
        if not isinstance(value, str) or not cls.PATTERN.fullmatch(value):
            raise ValueError(f"{value!r} is not an actor id like 'blue' or 'blue.tibbers'")
        return cls(value)

    @classmethod
    def __modify_schema__(cls, field_schema: dict) -> None:
        field_schema.update(type="string", pattern=cls.PATTERN.pattern)

    @property
    def team(self) -> "Actor":
        return Actor(self.split(".", 1)[0])


Actor.BLUE = Actor("blue")
Actor.RED = Actor("red")

#Champions

class AdaptiveType(str, Enum):
    """Decides adaptive force when bonus AD and AP are equal (wiki: each champion's page)."""
    PHYSICAL="physical"
    MAGIC="magic"


class RangeType(str, Enum):
    MELEE="Melee"
    RANGED="Ranged"

class ResourceType(str, Enum):
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
    NONE="None"


#Items

class ItemClass(str, Enum):
    ADV_CONSUMABLE="advanced consumable item"
    BASIC="Basic"
    BOOTS="boots item"
    CONSUMABLE="consumable item"
    DISTRIBUTED="distributed item"
    EPIC="epic item"
    LEGENDARY="legendary item"
    MASTERWORK="masterwork item"
    NONE="None"
    OUTDATED="outdated"
    STARTER="starter item"
    TRINKET="trinket item"
    TOWER_MINION="tower and minion item"


#Ability details

class DamageType(str, Enum):
    ABILITY="Ability damage"
    AOE="Area damage"
    AOE_DOT="AOE DOT damage"
    BASIC="Basic damage"
    DOT="DOT damage"
    PET="Pet damage"
    PROC="Proc damage"
    REACTIVE="Reactive damage"  # Thornmail: reacts to being hit
    ON_HIT="On-hit damage"  # applies life steal like basic damage (Mist's Edge, Spellblade)

class DamageSubType(str, Enum):
    PHYSIC = "Physical"
    MAGIC = "Magic"
    TRUE = "True"
    ADAPTIVE = "Adaptive"


#Abilities


class ActiveType(str, Enum):
    ACTIVE="Active"
    CONSUME="Consume"


#Effects

class EffectType(str, Enum):
    DAMAGE="Damage"
    HEAL="Heal"
    SHIELD="Shield"
    STATUS="Status"
    COST="Cost"
    REGEN="Regen"

class OriginKind(str, Enum):
    ABILITY = "ability"
    PASSIVE = "passive"
    ATTACK = "attack"
    SUMMONER = "summoner"
    ITEM = "item"
    RUNE = "rune"
    REGEN = "regen"
    VAMP = "vamp"  # life steal heals; later omnivamp



class CostResource(str, Enum):
    """What an ability costs; not the same as the champion's resource bar (Vladimir's bar is Crimson Rush, his costs are health)."""
    NONE="none"
    HEALTH="health"
    MANA="mana"
    ENERGY="energy"

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
    UNTARGETABLE = "Untargetable"
    GRIEVOUS_WOUNDS = "Grievous Wounds"  # strength = healing reduction, the strongest counts
    SUSPENSION = "Suspension"
    TAUNT = "Taunt"




class Comparison(str, Enum):
    GT="Greater than"
    LT="Less than"
    EQ="Equal"
    GE="Greater or equal"
    LE="Less or equal"


class Trigger(str, Enum):
    ON_CAST = "on_cast"
    ON_ATTACK = "on_attack"
    ON_HIT = "on_hit"
    ON_DAMAGE_DEALT = "on_damage_dealt"
    ON_GET_HIT = "on_get_hit"
    ON_INTERVAL = "on_interval"
    ON_STACK = "on_stack"
    ON_START = "on_start"
    ON_DAMAGE_TAKEN = "on_damage_taken"
    ON_DEBUFF_DEALT = "on_debuff_dealt"  # a status (CC, Grievous Wounds) or a DoT applied to an enemy (Electrocute)

class Target(str, Enum):
    SELF = "self"
    TARGET = "target"
    BEARER = "bearer"
    PET = "pet"
    OWNER = "owner"
    ENEMY = "enemy"  # the enemy champion; auras hit it from a buff on their source

class RuleActionType(str, Enum):
    DAMAGE = "Damage"
    HEAL = "Heal"
    SHIELD = "Shield"
    STATUS = "Status"
    APPLY_BUFF = "ApplyBuff"
    REMOVE_BUFF = "RemoveBuff"
    RESET_ATTACK = "ResetAttack"
    MODIFY_COOLDOWN = "ModifyCooldown"
    SUMMON = "Summon"
    PAY_COST = "PayCost"
    CLEANSE = "Cleanse"
    LOCK = "Lock"
    EXECUTE = "Execute"
    ATTACK = "Attack"
    TOGGLE_BUFF = "ToggleBuff"
    CUSTOM = "Custom"

class StatMode(str, Enum):
    FLAT = "flat"
    PERCENT = "percent"


class ErrorCode(str, Enum):
    """What kind of failure an error response is, so the UI can react without parsing messages."""
    INVALID_COMBO = "invalid_combo"  # the request can't be simulated (not enough mana, item without an active)
    INVALID_DATA = "invalid_data"  # the entered data is broken (formula, unknown buff)
    NOT_ENTERED = "not_entered"  # an ability without data yet
    NOT_SUPPORTED = "not_supported"  # the simulation can't do this yet
    INTERNAL = "internal"  # a bug


class ChangeSource(str, Enum):
    DATA = "data"  # the loader's diff of CommunityDragon's data
    PATCH_NOTES = "patch_notes"  # a line from the wiki's patch notes
