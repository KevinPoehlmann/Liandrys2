"""Which patches to load: Riot's version list (newest first) against the latest patch in the database, and whether
the PBE preview needs a reload."""
import re

from src.server.loader.helper import SafeSession, patch_sort_key
from src.server.loader.patchexceptions import PatcherError
from src.server.models.json_validation import ChampionJson
from src.server.models.patch import NewPatch


DDRAGON_VERSIONS = "https://ddragon.leagueoflegends.com/api/versions.json"
MODE_CHAMPION_IDS = 10000  # the client also lists mode copies (Swiftplay's Jade_Annie is 60001)


async def fetch_patch_list(session: SafeSession) -> list[str]:
    patches = await session.get_json(DDRAGON_VERSIONS)
    if not (isinstance(patches, list) and len(patches) >= 2 and all(isinstance(patch, str) for patch in patches)):
        raise PatcherError("versions.json is missing or in the wrong shape", "Couldn't validate versions.json")
    return patches


def is_complete(patch: NewPatch | None) -> bool:
    return patch is not None and patch.loaded_total_count == patch.total_count


def patches_to_load(latest: NewPatch | None, riot_patches: list[str]) -> list[str]:
    """Oldest first: the ones newer than the database, plus the latest one if its load is unfinished."""
    if latest is None:
        return [riot_patches[0]]
    try:
        index = riot_patches.index(latest.patch)
    except ValueError:
        raise PatcherError(f"Patch {latest.patch} not found in Riot's list. Investigate what changed.",
                           "Patch not found in patch list.")
    newer = riot_patches[:index] if is_complete(latest) else riot_patches[:index + 1]
    return sorted(newer, key=patch_sort_key)


def preview_name(build: str) -> str:
    """The patch a PBE build previews ("16.24.8420984+branch.main.content.beta" ⇒ "16.24.1"): Riot releases every
    patch as .1 first, and the preview takes the name it will have."""
    match = re.match(r"(\d+)\.(\d+)\.", build)
    if not match:
        raise PatcherError(f"PBE build {build} has no version", "Couldn't read the PBE's version")
    return f"{match[1]}.{match[2]}.1"


def is_newer(patch: str, than: str) -> bool:
    return patch_sort_key(patch) > patch_sort_key(than)


def preview_is_current(preview: NewPatch | None, name: str, build: str, live: NewPatch) -> bool:
    """The stored preview shows this PBE build and the live patch it was built from (that patch's load or last hotfix
    came before it). Its build is only stored once the load has run, so an interrupted load is never current."""
    if preview is None or preview.patch != name or preview.build != build:
        return False
    return (live.updated_at or live.timestamp) < preview.timestamp


def new_on_pbe(summary: list[dict], champions: list[ChampionJson]) -> list[str]:
    """Champions in the PBE client's list that the live list lacks; the preview leaves them out."""
    live = {int(champion.key) for champion in champions}
    return [entry["alias"] for entry in summary
            if 0 < entry.get("id", 0) < MODE_CHAMPION_IDS and entry["id"] not in live]
