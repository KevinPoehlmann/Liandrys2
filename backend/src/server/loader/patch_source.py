"""Which patches to load: Riot's version list (newest first) against the latest patch in the database."""
from src.server.loader.helper import SafeSession, patch_sort_key
from src.server.loader.patchexceptions import PatcherError
from src.server.models.patch import NewPatch


DDRAGON_VERSIONS = "https://ddragon.leagueoflegends.com/api/versions.json"


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
