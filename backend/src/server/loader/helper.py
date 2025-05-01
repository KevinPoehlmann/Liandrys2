import aiohttp
import asyncio
import functools
import json
import logging
import math
import re
import requests


from aiohttp import ClientResponseError
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable

from src.server.loader.patchexceptions import PatcherError, ScrapeError
from src.server.models.dataenums import HpScaling, Stat, DamageSubType
from src.server.models.effect import EffectType
from src.server.models.json_validation import (
    InfoJson,
    RuneJson
)


patch_logger = logging.getLogger("patch_loader")
debugger = logging.getLogger("debugger")



def info_loader() -> InfoJson:
    try:
        with open("src/server/loader/info.json") as info_file:
            info_dict = json.load(info_file)
        return InfoJson(**info_dict)
    except Exception as e:
        raise RuntimeError(f"Failed to load info.json: {e}")



def riot_to_wiki_patch(riot_patch: str) -> str:
    if not isinstance(riot_patch, str):
        raise PatcherError(f"Invalid riot patch format: {riot_patch}", f"Can't convert patch {riot_patch} to wiki format.")

    match = re.fullmatch(r"(\d+)\.(\d+)\.\d+", riot_patch)
    if not match:
        raise PatcherError(f"Invalid riot patch format: {riot_patch}", f"Can't convert patch {riot_patch} to wiki format.")

    season, patch = match.group(1), match.group(2)
    season = int(season) + 10
    patch = patch.zfill(2)
    return f"V{season}.{patch}"

def wiki_to_riot_patch(wiki_patch: str) -> str:
    if not isinstance(wiki_patch, str) or not wiki_patch.lower().startswith("v"):
        raise PatcherError(f"Invalid wiki patch format: {wiki_patch}", f"Can't convert patch {wiki_patch} to Riot format.")

    match_normal = re.fullmatch(r"[vV](\d+)\.(\d+)", wiki_patch)
    if match_normal:
        season = int(match_normal.group(1))
        patch = str(int(match_normal.group(2)))  # remove leading zero
        if season >= 20:
            season -= 10
        return f"{season}.{patch}.1"

    # V25.S1.3
    match_special = re.fullmatch(r"[vV](\d+)\.S(\d+)\.(\d+)", wiki_patch)
    if match_special:
        season = int(match_special.group(1))
        patch = str(int(match_special.group(3)))  # the last number becomes the patch
        if season >= 20:
            season -= 10
        return f"{season}.{patch}.1"

    raise PatcherError(f"Invalid wiki patch format: {wiki_patch}", f"Can't convert patch {wiki_patch} to Riot format.")







def parse_formula_from_table(bot_values: str, top_values: str = "", scale: str = "level") -> str:
    bot_values = [float(v.strip()) for v in bot_values.split(";")]
    if top_values:
        top_values = [float(v.strip()) for v in top_values.split(";")]
    else:
        top_values = list(range(1, len(bot_values) + 1))

    step = (bot_values[-1] - bot_values[0]) / (len(bot_values) - 1)
    top_step = (top_values[-1] - top_values[0]) / (len(top_values) - 1)
    if not math.isclose(step, bot_values[1] - bot_values[0], rel_tol=0.01) or not math.isclose(top_step, top_values[1] - top_values[0], rel_tol=0.01):
        return ""
    
    formula = f"{bot_values[0]} + (({scale} - {top_values[0]}) // {top_step}) * {step}"
    return formula


def parse_formula_from_string(string: str, scale: str = "rank") -> str:

    regex = r"(?P<values>[\d/ \.]+)(?P<unit>[\w]*)"
    match = re.fullmatch(regex, string)
    if not match:
        return string
    
    values = [float(v.strip()) for v in match.group("values").split("/")]
    if len(values) == 1:
        return f"{values[0]}"
    elif len(values) > 1:
        step = (values[-1] - values[0]) / (len(values) - 1)
        return f"{values[0]} + ({scale} - 1) * {step}"
    else:
        return string
    


def parse_formula_from_list(values: list[float], scale: str = "rank") -> str:
    formula = ""
    if len(values) == 1:
        formula = f"{values[0]}"
    else:
        step = (values[-1] - values[0]) / (len(values) - 1)
        formula = f"{values[0]} + ({scale} - 1) * {step}"
    return formula



def parse_effect_formula(string: str) -> tuple[str, HpScaling]:
    parentheses = r"(\(\+\s*)?"
    values_reg = r"(?P<values>[\d/\.\s]+)"
    percent = r"(?P<percent>%\s*)?"
    multi = r"(?P<multi>\(\+\s[^\)]*\)\s*)?"
    unit = r"(?P<unit>[\w'\s]+)?"
    regex = parentheses + values_reg + percent + multi + unit + r"\)?"

    hp_scaling = HpScaling.FLAT

    match = re.fullmatch(regex, string)
    if not match:
        return string, hp_scaling
    values = [float(v.strip()) for v in match.group("values").split("/")]
    
    if match.group("unit"):
        stat, hp_scaling, perc = find_stat(match.group("unit"))
        if stat == Stat.ERROR:
            return string, hp_scaling
        if perc:
            values = [v / 100 for v in values]

    if match.group("percent"):
        values = [v / 100 for v in values]
    
    formula = parse_formula_from_list(values, scale="rank")
    

    if match.group("multi"):
        multi_re = parentheses + values_reg + percent + unit + r"\)?"
        multi_match = re.fullmatch(multi_re, match.group("multi").strip())
        if not multi_match:
            return string, hp_scaling
        multi_values = [float(v.strip()) for v in multi_match.group("values").split("/")]

        if multi_match.group("unit"):
            multi_stat, _, multi_perc = find_stat(multi_match.group("unit"))
            if multi_stat == Stat.ERROR:
                return string, hp_scaling
            if multi_perc:
                multi_values = [v / 100 for v in multi_values]

        if multi_match.group("percent"):
            multi_values = [v / 100 for v in multi_values]

        multi_formula = parse_formula_from_list(multi_values, scale="rank")

        if multi_match.group("unit") and multi_stat != Stat.FLAT:
            multi_formula = f"({multi_formula}) * {multi_stat.value}"
        formula = f"{formula} + {multi_formula}"

    if match.group("unit") and stat != Stat.FLAT:
        formula = f"({formula}) * {stat.value}"

    return formula, hp_scaling



def find_stat(stat: str) -> tuple[Stat, HpScaling, bool]:
    stat_enum = Stat.FLAT
    hp_scale = HpScaling.FLAT
    percent = False
    stat = stat.lower()
    if "per 100" in stat:
        stat = stat.replace("per 100", "")
        percent = True
    if "of target's" in stat:
        stat = stat.replace("of target's", "")
        if "maximum health" in stat:
            stat = stat.replace("maximum health", "")
            hp_scale = HpScaling.MAX_HP
        elif "current health" in stat:
            stat = stat.replace("current health", "")
            hp_scale = HpScaling.CURRENT_HP
        elif "missing health" in stat:
            stat = stat.replace("missing health", "")
            hp_scale = HpScaling.MISSING_HP
    stat = stat.strip()
    if stat:
        try:
            stat_enum = Stat(stat)
        except ValueError as e:
            stat_enum = Stat.ERROR
            patch_logger.warning(f"Unknown stat: {stat}. Error: {e}")

    return stat_enum, hp_scale, percent


def contains_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text.lower()) is not None


def find_label(label: str) -> tuple[EffectType, DamageSubType]:
    label = label.lower()
    damage_subtype = DamageSubType.TRUE

    if contains_word(label, "magic"):
        damage_subtype = DamageSubType.MAGIC
    elif contains_word(label, "physical"):
        damage_subtype = DamageSubType.PHYSIC

    if "damage" in label:
        effect_type = EffectType.DAMAGE
        if contains_word(label, "true"):
            damage_subtype = DamageSubType.TRUE
    elif contains_word(label, "heal"):
        effect_type = EffectType.HEAL
    elif contains_word(label, "shield"):
        effect_type = EffectType.SHIELD
    else:
        raise ScrapeError(f"Can't find effect type for {label}.", "Champion", "Unknown")

    return effect_type, damage_subtype


def wiki_to_datetime(wiki_patch: str) -> datetime:
    months = {
        "January": "1",
        "February": "2",
        "March": "3",
        "April": "4",
        "May": "5",
        "June": "6",
        "July": "7",
        "August": "8",
        "September": "9",
        "October": "10",
        "November": "11",
        "December": "12"
    }

    cleaned = re.sub(r"(st|nd|rd|th)", "", wiki_patch.replace("Hotfix", "")).strip()
    parts = cleaned.split()

    if len(parts) != 2:
        raise ScrapeError(f"Unexpected date format: '{wiki_patch}", "Patch", "Hotfix")

    month_str, day_str = parts
    month_num = months.get(month_str)
    if not month_num:
        raise ValueError(f"Unknown month name: '{month_str}'")

    day = day_str.zfill(2)
    year = str(datetime.now().year)
    try:
        hotfix_date = datetime.strptime(f"{year}-{month_num}-{day}", "%Y-%m-%d")
        return hotfix_date
    except ValueError as e:
        raise ScrapeError(f"Error parsing date: {wiki_patch}", "Patch", "Hotfix")


def datetime_to_wiki(date: datetime) -> str:
    day = date.day
    month = date.strftime("%B")  # Full month name like "March"

    # Add suffix
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    return f"{month} {day}{suffix} Hotfix"



class TodoType(str, Enum):
    LOAD="Load"
    HOTFIX="Hotfix"
    PATCH="Patch"



@dataclass
class Todo():
    todo_type: TodoType
    patch: str
    hotfix: datetime = None



@dataclass
class RuneClass():
    """Class to gather Rune information"""
    rune: RuneJson
    tree: str
    tree_id: int
    row: int

    def __str__(self) -> str:
        return self.rune.name


class SafeSession:
    def __init__(self, session: aiohttp.ClientSession, max_retries: int = 3, backoff_factor: float = 1.5):
        self.session = session
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def _retry(retries=3, base_delay=1.5):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                for attempt in range(1, retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except (aiohttp.ClientResponseError, requests.RequestException) as e:
                        if getattr(e, 'status', None) == 429:
                            delay = base_delay * 2 ** (attempt - 1)
                            patch_logger.warning(f"Rate limited (429). Retrying in {delay:.2f}s... [{attempt}/{retries}]")
                            await asyncio.sleep(delay)
                            continue
                        raise
                raise RuntimeError("Max retry attempts exceeded.")
            return wrapper
        return decorator

    @_retry()
    async def get_json(self, url: str) -> dict:
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    @_retry()
    async def get_html(self, url: str) -> str:
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.text()

    @_retry()
    async def get_bytes(self, url: str) -> bytes:
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.read()