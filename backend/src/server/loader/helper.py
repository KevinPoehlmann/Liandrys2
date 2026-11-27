import aiohttp
import asyncio
import functools
import json
import logging
import re
import time


from datetime import datetime

from src.server.loader.patchexceptions import PatcherError, ScrapeError
from src.server.models.json_validation import InfoJson

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

def patch_sort_key(patch: str) -> tuple[int, ...]:
    return tuple(int(part) for part in patch.split("."))

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







def _remove_day_suffixes(text: str) -> str:
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)


def wiki_release_to_datetime(wiki_release: str) -> datetime:
    cleaned = _remove_day_suffixes(wiki_release).strip()
    try:
        return datetime.strptime(cleaned, "%B %d, %Y")
    except ValueError:
        raise ScrapeError(f"Unexpected release date format: '{wiki_release}'", "Patch", "Release")


def wiki_to_datetime(wiki_hotfix: str, release_date: datetime) -> datetime:
    cleaned = _remove_day_suffixes(wiki_hotfix.replace("Hotfix", "")).strip()
    try:
        hotfix_date = datetime.strptime(f"{cleaned} {release_date.year}", "%B %d %Y")
    except ValueError:
        raise ScrapeError(f"Unexpected date format: '{wiki_hotfix}'", "Patch", "Hotfix")

    # Hotfix dates have no year: a December patch can get its hotfix in January
    if hotfix_date < release_date:
        hotfix_date = hotfix_date.replace(year=release_date.year + 1)
    return hotfix_date


def datetime_to_wiki(date: datetime) -> str:
    day = date.day
    month = date.strftime("%B")  # Full month name like "March"

    # Add suffix
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    return f"{month} {day}{suffix} Hotfix"










class SafeSession:
    def __init__(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore | None = None, max_retries: int = 3, backoff_factor: float = 25, backoff_event: asyncio.Event | None = None):
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
                    delay = base_delay * 2 ** (attempt - 1)
                    last = attempt == retries
                    next_step = "Giving up." if last else f"Retrying in {delay:.2f}s..."

                    async def wait():
                        if not last:
                            await asyncio.sleep(delay)

                    try:
                        return await func(*args, **kwargs)
                    except aiohttp.ClientResponseError as e:
                        url = str(getattr(getattr(e, 'request_info', None), 'real_url', ''))
                        if e.status == 429:
                            if hasattr(self, "http_429_abortion"):
                                await self.http_429_abortion()
                            if not last and hasattr(self, '_global_backoff'):
                                await self._global_backoff(delay)
                            patch_logger.info(f"[NETWORK] [RETRY] [429] Rate limited. {next_step} [{attempt}/{retries}]")
                            if attempt == 1 or last:
                                load_logger.warning(f"[NETWORK] [RETRY] [429] Rate limited. {next_step} [{attempt}/{retries}]")
                            continue
                        if e.status == 404:
                            patch_logger.warning(f"[NETWORK] [RETRY] [404] Not found: {url}")
                            return ""
                        if e.status in (403, 401):
                            if hasattr(self, "abort_event"):
                                self.abort_event.set()
                                patch_logger.critical(f"[NETWORK] [RETRY] [{e.status}] Access denied at {url}. Aborting further requests.")
                            raise RuntimeError(f"Access forbidden: HTTP {e.status}") from e
                        if e.status >= 500:
                            patch_logger.warning(f"[NETWORK] [RETRY] [{e.status}] Server error. {next_step} [{attempt}/{retries}]")
                            await wait()
                            continue
                        raise
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        # Dropped connections and timeouts are transient; anything else is a bug and passes through.
                        patch_logger.warning(f"[NETWORK] [RETRY] [{type(e).__name__}] {e}. {next_step} [{attempt}/{retries}]")
                        await wait()
                raise RuntimeError("Max retry attempts exceeded.")
            return wrapper
        return decorator

    @_retry()
    async def get_json(self, url: str) -> dict:
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            return await response.json()

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
        self.recent_429s = [t for t in self.recent_429s if now - t < 80]
        if len(self.recent_429s) >= 16:
            patch_logger.critical("[NETWORK] [RETRY] [429] Too many 429 responses in the last minute. Aborting further requests.")
            self.abort_event.set()
            if not self.backoff_event.is_set():
                self.backoff_event.set()
            raise RuntimeError("Too many 429 responses, aborting further requests.")
        else:
            patch_logger.info(f"[NETWORK] [RETRY] [429] Recent 429 count: {len(self.recent_429s)}")