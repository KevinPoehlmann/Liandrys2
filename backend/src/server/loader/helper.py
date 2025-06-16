import aiohttp
import asyncio
import functools
import json
import logging
import math
import re
import requests
import socket
import time


from aiohttp import ClientResponseError
from dataclasses import dataclass
from datetime import datetime

from src.server.loader.patchexceptions import PatcherError, ScrapeError
from src.server.models.dataenums import HpScaling, Stat, DamageSubType
from src.server.models.effect import EffectType
from src.server.models.json_validation import (
    InfoJson,
    RuneJson
)

patch_logger = logging.getLogger("liandrys.patch")
load_logger = logging.getLogger("liandrys.load")
debug_logger = logging.getLogger("liandrys.debug")



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







def parse_formula_from_table(bot_str: str, top_str: str = "", scale: str = "level") -> str:
    bot_values = [float(v.strip()) for v in bot_str.split(";")]
    if top_str:
        top_values = [float(v.strip()) for v in top_str.split(";")]
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
            patch_logger.warning(f"[CHAMPION] [SCRAPE] [?] Unknown stat: {stat}. Error: {e}")

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




@dataclass
class RuneClass():
    """Class to gather Rune information"""
    rune: RuneJson
    tree: str
    tree_id: int
    row: int

    def __str__(self) -> str:
        return self.rune.name




RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientResponseError,
    aiohttp.ClientConnectorError,
    aiohttp.ServerDisconnectedError,
    requests.RequestException,
    asyncio.TimeoutError,
    socket.gaierror,  # DNS failure
    OSError  # very low-level failures
)


class SafeSession:
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore | None = None, max_retries: int = 3, backoff_factor: float = 10, backoff_event: asyncio.Event | None = None):
        self.session = session
        self.semaphore = semaphore or asyncio.Semaphore(5)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.backoff_event = backoff_event or asyncio.Event()
        self.backoff_event.set()
        self.abort_event = asyncio.Event()
        self.recent_429s: list[float] = []

    @staticmethod
    def _retry():
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                self = args[0]
                retries = getattr(self, "max_retries", 3)
                base_delay = getattr(self, "backoff_factor", 1.5)
                for attempt in range(1, retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if isinstance(e, aiohttp.ClientResponseError):
                            delay = base_delay * 2 ** (attempt - 1)
                            if e.status == 429:
                                if hasattr(self, "http_429_abortion"):
                                    await self.http_429_abortion()
                                if hasattr(self, '_global_backoff'):
                                    await self._global_backoff(delay)
                                patch_logger.info(f"[NETWORK] [RETRY] [429] Rate limited. Retrying in {delay:.2f}s... [{attempt}/{retries}]")
                                if attempt == 1 or attempt == retries:
                                    load_logger.warning(f"[NETWORK] [RETRY] [429] Rate limited. Retrying in {delay:.2f}s... [{attempt}/{retries}]")
                                continue
                            elif e.status == 404:
                                patch_logger.warning(f"[NETWORK] [RETRY] [404] Not found: {str(getattr(getattr(e, 'request_info', None), 'real_url', ''))}")
                                return ""
                            elif e.status in (403, 401):
                                if hasattr(self, "abort_event"):
                                    self.abort_event.set()
                                    patch_logger.critical(f"[NETWORK] [RETRY] [{e.status}] Access denied at {str(getattr(getattr(e, 'request_info', None), 'real_url', ''))}. Aborting further requests.")
                                raise RuntimeError(f"Access forbidden: HTTP {e.status}") from e
                            elif e.status >= 500:
                                patch_logger.warning(f"[NETWORK] [RETRY] [{e.status}] Server error. Retrying in {base_delay * 2 ** (attempt - 1):.2f}s... [{attempt}/{retries}]")
                                await asyncio.sleep(delay)
                                continue
                raise RuntimeError("Max retry attempts exceeded.")
            return wrapper
        return decorator

    @_retry()
    async def get_json(self, url: str) -> dict:
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            return await response.json()

    @_retry()
    async def get_html(self, url: str) -> str:
        async with self.semaphore:
            if self.abort_event.is_set():
                return ""
            await self.backoff_event.wait()
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                response.raise_for_status()
                return await response.text()

    @_retry()
    async def get_bytes(self, url: str) -> bytes:
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            return await response.read()
        

    async def _global_backoff(self, delay: float) -> None:
        if self.backoff_event.is_set():
            patch_logger.info(f"[NETWORK] [BACKOFF] [429] Global backoff for {delay:.2f}s")
            self.backoff_event.clear()  # block other tasks
            await asyncio.sleep(delay)
            self.backoff_event.set()
            patch_logger.info(f"[NETWORK] [BACKOFF] [429] Global backoff ended")


    async def http_429_abortion(self) -> None:
        now = time.monotonic()
        self.recent_429s.append(now)
        self.recent_429s = [t for t in self.recent_429s if now - t < 60]
        if len(self.recent_429s) >= 11:
            patch_logger.critical("[NETWORK] [RETRY] [429] Too many 429 responses in the last minute. Aborting further requests.")
            self.abort_event.clear()
            self.backoff_event.clear()
            raise RuntimeError("Too many 429 responses, aborting further requests.")
        else:
            patch_logger.info(f"[NETWORK] [RETRY] [429] Recent 429 count: {len(self.recent_429s)}")