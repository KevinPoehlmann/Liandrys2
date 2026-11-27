"""Downloads images from CommunityDragon and stores each under a hash of its pixels: the same image keeps its file,
a changed image gets a new one, so every patch points to its own image and nothing is ever renamed or deleted."""
import hashlib
import io
from pathlib import Path

from PIL import Image as PillowImage, UnidentifiedImageError

from src.server.loader.champion_builder import SLOTS, own_icons, spell_icons
from src.server.loader.champion_source import CDRAGON
from src.server.loader.helper import SafeSession
from src.server.loader.patchexceptions import LoadError
from src.server.models.champion import NewChampion, RawChampion
from src.server.models.image import Image
from src.server.models.item import NewItem, RawItem
from src.server.models.patch import NewPatch, RuneTree
from src.server.models.rune import NewRune, RawRune
from src.server.models.summonerspell import NewSummonerspell, RawSummonerspell


IMAGE_DIR = Path("src/images")
ORNN_MODIFIER = "Items/ItemModifiers/OrnnItemsModifier"
CLIENT_DATA = "plugins/rcp-be-lol-game-data/global/default/"
CLIENT_ASSETS = "/lol-game-data/assets/"


def asset_url(version: str, asset: str) -> str:
    # CDragon serves the game's .dds/.tex textures as .png under the lowercased path.
    return f"{CDRAGON}{version}/game/{asset.lower().rsplit('.', 1)[0]}.png"


def champion_icon_url(version: str, key: str) -> str:
    return f"{CDRAGON}{version}/{CLIENT_DATA}v1/champion-icons/{key}.png"


def champion_data_url(version: str, key: str) -> str:
    return f"{CDRAGON}{version}/{CLIENT_DATA}v1/champions/{key}.json"


def client_asset_url(version: str, path: str) -> str:
    # The client names its files "/lol-game-data/assets/ASSETS/...", CDragon serves them lowercased under the plugin.
    return f"{CDRAGON}{version}/{CLIENT_DATA}{path.removeprefix(CLIENT_ASSETS).lower()}"


def summoner_icon_url(version: str, asset: str) -> str:
    # Summoner spells name only the file ("SummonerIgnite.dds"); it lives with the other spell icons.
    return f"{CDRAGON}{version}/game/data/spells/icons2d/{_asset_name(asset)}.png"


def hashed_name(name: str, content: bytes, extension: str = "png") -> str:
    return f"{name}.{pixel_hash(content)}.{extension}"


def pixel_hash(content: bytes) -> str:
    """The pixels, not the file: Cloudflare serves CDragon's files sometimes recompressed ("Polish"), with other bytes,
    sometimes RGBA instead of RGB, and zeroed colors under fully transparent pixels."""
    with PillowImage.open(io.BytesIO(content)) as image:
        rgba = image.convert("RGBA")
    invisible = rgba.getchannel("A").point(lambda alpha: 255 if alpha == 0 else 0)
    rgba.paste((0, 0, 0, 0), mask=invisible)
    return hashlib.sha256(rgba.tobytes()).hexdigest()[:8]


async def store_image(session: SafeSession, url: str, group: str, name: str) -> Image:
    content = await session.get_bytes(url)
    if not content:  # SafeSession answers a 404 with ""
        raise LoadError(404, "Image not found", url, group, name)
    try:
        image = Image(full=hashed_name(name, content, url.rsplit(".", 1)[-1]), group=group)
    except UnidentifiedImageError:  # an error page instead of the image
        raise LoadError(415, "Not an image", url, group, name)
    path = IMAGE_DIR / group / image.full
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return image


async def load_champion_images(session: SafeSession, champion: NewChampion, raw: RawChampion, version: str) -> list[str]:
    """Points the champion, its abilities and its icon list to stored CDragon images, and each extra ability to the
    icon it names. Returns what failed; those keep their old image."""
    failures = []
    stored: dict[str, Image | None] = {}  # by URL: a slot's icon is in the icon list too, and a failure is reported once

    async def store(url: str, group: str, name: str) -> Image | None:
        if url not in stored:
            stored[url] = await _stored_or_failure(session, url, group, name, failures)
        return stored[url]

    champion.image = await store(champion_icon_url(version, champion.key), "champion",
                                 champion.champion_id.lower()) or champion.image
    for slot, asset in spell_icons(raw).items():
        if not asset:
            failures.append(f"{slot}: no icon in the spell data")
            continue
        owner = getattr(champion, slot)
        group = "passive" if slot == "passive" else "spell"
        owner.image = await store(asset_url(version, asset), group, _asset_name(asset)) or owner.image
    for asset in own_icons(raw):
        if image := await store(asset_url(version, asset), "spell", _asset_name(asset)):
            champion.icons[_asset_name(asset)] = image
    champion.splash = await _splash(session, champion, version, failures) or champion.splash
    return failures + _link_icons(champion)


async def _splash(session: SafeSession, champion: NewChampion, version: str, failures: list[str]) -> Image | None:
    """The base skin's centered splash art (1280×720). Its path is in the client's champion file, not in a fixed
    pattern (Hwei's lies under Skin0 instead of Base)."""
    url = champion_data_url(version, champion.key)
    try:
        data = await session.get_json(url)
    except RuntimeError as e:  # SafeSession's retries are used up
        failures.append(f"splash: {e} — {url}")
        return None
    path = next((skin.get("splashPath") for skin in (data or {}).get("skins", []) if skin.get("isBase")), None)
    if not path:
        failures.append(f"splash: no base skin splash — {url}")
        return None
    return await _stored_or_failure(session, client_asset_url(version, path), "splash", champion.champion_id.lower(),
                                    failures)


async def _stored_or_failure(session: SafeSession, url: str, group: str, name: str, failures: list[str]) -> Image | None:
    try:
        return await store_image(session, url, group, name)
    except LoadError as e:
        failures.append(f"{group} {name}: {e.code} {e.reason} — {e.url}")
    except RuntimeError as e:  # SafeSession's retries are used up
        failures.append(f"{group} {name}: {e} — {url}")
    return None


def _link_icons(champion: NewChampion) -> list[str]:
    """Extra abilities get the image of their icon key. Stages keep only the key, the frontends look it up.
    A key the icons lack (Riot renamed the file) is reported, and its owner keeps the old image."""
    for extra in champion.extra_abilities:
        if extra.icon in champion.icons:
            extra.image = champion.icons[extra.icon]
    abilities = [getattr(champion, slot) for slot in SLOTS] + champion.extra_abilities
    keys = [(extra.name, extra.icon) for extra in champion.extra_abilities]
    keys += [(f"{ability.name} stage {number}", stage.icon)
             for ability in abilities for number, stage in enumerate(ability.stages, start=1)]
    return [f"{owner}: icon '{key}' is not in the champion's icons" for owner, key in keys
            if key and key not in champion.icons]


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


async def load_item_image(session: SafeSession, item: NewItem, raw: RawItem, version: str) -> list[str]:
    """Like load_summonerspell_image: the failure, if any; then the item keeps Data Dragon's image."""
    asset = raw.cdragon.get("mItemDataClient", {}).get("inventoryIcon", "")
    if not asset:
        return ["no icon in the item data"]
    url = asset_url(version, asset)
    try:
        item.image = await store_image(session, url, "item", _asset_name(asset))
    except LoadError as e:
        return [f"{e.code} {e.reason} — {e.url}"]
    except RuntimeError as e:  # SafeSession's retries are used up
        return [f"{e} — {url}"]
    return []


async def load_rune_image(session: SafeSession, rune: NewRune, raw: RawRune, version: str) -> list[str]:
    """Like load_item_image: the failure, if any; then the rune keeps Data Dragon's image."""
    asset = raw.cdragon.get("mIconTextureName", "")
    if not asset:
        return ["no icon in the rune data"]
    url = asset_url(version, asset)
    try:
        rune.image = await store_image(session, url, "rune", _asset_name(asset))
    except LoadError as e:
        return [f"{e.code} {e.reason} — {e.url}"]
    except RuntimeError as e:  # SafeSession's retries are used up
        return [f"{e} — {url}"]
    return []


async def load_masterwork_border(session: SafeSession, patch: NewPatch, items_bin: dict, version: str) -> list[str]:
    """Ornn's upgrade only changes an item's numbers and its frame, an overlay with a transparent middle."""
    asset = items_bin.get(ORNN_MODIFIER, {}).get("inventoryIconToOverlay", "")
    if not asset:
        return [f"no overlay in {ORNN_MODIFIER}"]
    url = asset_url(version, asset)
    try:
        patch.masterwork_border = await store_image(session, url, "item", _asset_name(asset))
    except LoadError as e:
        return [f"{e.code} {e.reason} — {e.url}"]
    except RuntimeError as e:  # SafeSession's retries are used up
        return [f"{e} — {url}"]
    return []


async def load_rune_tree_icons(session: SafeSession, patch: NewPatch, trees: dict[int, tuple[str, str]],
                               version: str) -> list[str]:
    """The five trees' icons for the rune page. A tree whose icon fails is left out."""
    failures = []
    for tree_id, (name, asset) in trees.items():
        if not asset:
            failures.append(f"{name}: no icon in the tree data")
        elif image := await _stored_or_failure(session, asset_url(version, asset), "rune", _asset_name(asset), failures):
            patch.rune_trees[tree_id] = RuneTree(name=name, image=image)
    return failures


def _asset_name(asset: str) -> str:
    return asset.lower().rsplit("/", 1)[-1].rsplit(".", 1)[0]
