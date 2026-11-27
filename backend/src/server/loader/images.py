"""Downloads images from CommunityDragon and stores each under a hash of its content: the same image keeps its file,
a changed image gets a new one, so every patch points to its own image and nothing is ever renamed or deleted."""
import hashlib
from pathlib import Path

from src.server.loader.champion_builder import spell_icons
from src.server.loader.champion_source import CDRAGON
from src.server.loader.helper import SafeSession
from src.server.loader.patchexceptions import LoadError
from src.server.models.champion import NewChampion, RawChampion
from src.server.models.image import Image
from src.server.models.summonerspell import NewSummonerspell, RawSummonerspell


IMAGE_DIR = Path("src/images")


def asset_url(version: str, asset: str) -> str:
    # CDragon serves the game's .dds/.tex textures as .png under the lowercased path.
    return f"{CDRAGON}{version}/game/{asset.lower().rsplit('.', 1)[0]}.png"


def champion_icon_url(version: str, key: str) -> str:
    return f"{CDRAGON}{version}/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{key}.png"


def summoner_icon_url(version: str, asset: str) -> str:
    # Summoner spells name only the file ("SummonerIgnite.dds"); it lives with the other spell icons.
    return f"{CDRAGON}{version}/game/data/spells/icons2d/{_asset_name(asset)}.png"


def hashed_name(name: str, content: bytes) -> str:
    return f"{name}.{hashlib.sha256(content).hexdigest()[:8]}.png"


async def store_image(session: SafeSession, url: str, group: str, name: str) -> Image:
    content = await session.get_bytes(url)
    if not content:  # SafeSession answers a 404 with ""
        raise LoadError(404, "Image not found", url, group, name)
    image = Image(full=hashed_name(name, content), group=group)
    path = IMAGE_DIR / group / image.full
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return image


async def load_champion_images(session: SafeSession, champion: NewChampion, raw: RawChampion, version: str) -> list[str]:
    """Points the champion and its abilities to stored CDragon images. Returns what failed; those keep their old image."""
    targets = [(champion, champion_icon_url(version, champion.key), "champion", champion.champion_id.lower())]
    failures = []
    for slot, asset in spell_icons(raw).items():
        if not asset:
            failures.append(f"{slot}: no icon in the spell data")
            continue
        group = "passive" if slot == "passive" else "spell"
        targets.append((getattr(champion, slot), asset_url(version, asset), group, _asset_name(asset)))

    for owner, url, group, name in targets:
        try:
            owner.image = await store_image(session, url, group, name)
        except LoadError as e:
            failures.append(f"{group} {name}: {e.code} {e.reason} — {e.url}")
        except RuntimeError as e:  # SafeSession's retries are used up
            failures.append(f"{group} {name}: {e} — {url}")
    return failures


async def load_summonerspell_image(session: SafeSession, summonerspell: NewSummonerspell, raw: RawSummonerspell,
                                   version: str) -> list[str]:
    """Like load_champion_images: the failure, if any; then the spell keeps its old image."""
    asset = raw.cdragon["mSpell"].get("mImgIconName", [""])[0]
    if not asset:
        return ["no icon in the spell data"]
    url = summoner_icon_url(version, asset)
    try:
        summonerspell.image = await store_image(session, url, "spell", _asset_name(asset))
    except LoadError as e:
        return [f"{e.code} {e.reason} — {e.url}"]
    except RuntimeError as e:  # SafeSession's retries are used up
        return [f"{e} — {url}"]
    return []


def _asset_name(asset: str) -> str:
    return asset.lower().rsplit("/", 1)[-1].rsplit(".", 1)[0]
