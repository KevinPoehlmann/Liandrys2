import io
import json
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image as PillowImage

import src.server.loader.images as images
from src.server.loader.champion_builder import build_champion
from src.server.loader.item_builder import build_item
from src.server.loader.patchexceptions import LoadError
from src.server.models.champion import NewChampion, RawChampion
from src.server.models.image import Image
from src.server.models.json_validation import ChampionJson
from src.server.models.patch import NewPatch
from src.tests.test_item_builder import GUNBLADE
from src.tests.test_item_builder import entry as item_entry
from src.tests.test_item_builder import raw as item_raw


CDRAGON = Path(__file__).parent / "static" / "cdragon"
STRIKE_URL = "https://raw.communitydragon.org/16.23/game/assets/characters/veigar/hud/icons2d/veigarbalefulstrike.png"


def fixture(name: str) -> dict:
    return json.loads((CDRAGON / name).read_text(encoding="utf-8"))


def png(color: tuple[int, ...] = (200, 50, 50, 255), mode: str = "RGBA") -> bytes:
    buffer = io.BytesIO()
    PillowImage.new(mode, (2, 2), color).save(buffer, "PNG")
    return buffer.getvalue()


ICON, OTHER_ICON = png(), png((50, 200, 50, 255))


# The client's champion file, cut to its base skin (Veigar's).
CHAMPION_FILE = {"skins": [{"isBase": True, "splashPath": "/lol-game-data/assets/ASSETS/Characters/Veigar/Skins/Base/"
                                                         "Images/veigar_splash_centered_0.jpg"}]}


class FakeSession:
    """Answers like SafeSession: the bytes for known URLs, b"" for everything else (a 404); every JSON request
    gets `json`."""

    def __init__(self, responses: dict[str, bytes], json: dict | str = CHAMPION_FILE) -> None:
        self.responses = responses
        self.json = json
        self.urls: list[str] = []

    async def get_bytes(self, url: str) -> bytes:
        self.urls.append(url)
        return next((data for part, data in self.responses.items() if part in url), b"")

    async def get_json(self, url: str) -> dict | str:
        self.urls.append(url)
        return self.json


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(images, "IMAGE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def nidalee():
    raw = RawChampion(champion_id="Nidalee", patch="16.23.1", build="16.23.1", fetched_at=datetime(2026, 11, 24),
                      cdragon=fixture("nidalee.bin.json"))
    document = json.loads((CDRAGON.parent / "test_group" / "champions" / "nidalee.json").read_text(encoding="utf-8"))
    return NewChampion(**document), raw


@pytest.fixture
def veigar():
    raw = RawChampion(champion_id="Veigar", patch="16.23.1", build="16.23.1", fetched_at=datetime(2026, 11, 24),
                      cdragon=fixture("veigar.bin.json"))
    return build_champion(raw, ChampionJson(**fixture("veigar.ddragon.json"))), raw


def test_asset_url_is_the_lowercased_png():
    assert images.asset_url("16.23", "ASSETS/Characters/Veigar/HUD/Icons2D/VeigarBalefulStrike.dds") == STRIKE_URL


def test_champion_icon_by_key():
    assert images.champion_icon_url("16.23", "45").endswith("/16.23/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/45.png")


class TestStoreImage():

    @pytest.mark.asyncio
    async def test_name_carries_a_pixel_hash(self, image_dir):
        image = await images.store_image(FakeSession({"strike": ICON}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert (image.group, image.full) == ("spell", f"veigarbalefulstrike.{images.pixel_hash(ICON)}.png")
        assert (image_dir / "spell" / image.full).read_bytes() == ICON


    @pytest.mark.asyncio
    async def test_same_image_same_file(self, image_dir):
        session = FakeSession({"strike": ICON})

        first = await images.store_image(session, STRIKE_URL, "spell", "veigarbalefulstrike")
        second = await images.store_image(session, STRIKE_URL, "spell", "veigarbalefulstrike")

        assert first == second
        assert len(list((image_dir / "spell").iterdir())) == 1


    @pytest.mark.asyncio
    async def test_changed_image_gets_a_new_file_and_the_old_one_stays(self, image_dir):
        old = await images.store_image(FakeSession({"strike": ICON}), STRIKE_URL, "spell", "veigarbalefulstrike")
        new = await images.store_image(FakeSession({"strike": OTHER_ICON}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert old.full != new.full
        assert {path.name for path in (image_dir / "spell").iterdir()} == {old.full, new.full}


    @pytest.mark.asyncio
    async def test_a_recompressed_copy_keeps_the_file(self, image_dir):
        # Cloudflare's Polish: RGB saved as RGBA, colors under invisible pixels zeroed; the pixels stay the same.
        original = png((200, 50, 50), "RGB")
        first = await images.store_image(FakeSession({"strike": original}), STRIKE_URL, "spell", "veigarbalefulstrike")
        second = await images.store_image(FakeSession({"strike": png()}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert first == second
        assert images.pixel_hash(png((16, 4, 0, 0))) == images.pixel_hash(png((0, 0, 0, 0)))


    @pytest.mark.asyncio
    async def test_an_error_page_is_not_an_image(self, image_dir):
        with pytest.raises(LoadError) as error:
            await images.store_image(FakeSession({"strike": b"<html>"}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert error.value.code == 415
        assert not any(image_dir.iterdir())


    @pytest.mark.asyncio
    async def test_missing_image_is_a_load_error_and_writes_nothing(self, image_dir):
        with pytest.raises(LoadError):
            await images.store_image(FakeSession({}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert not any(image_dir.iterdir())


class TestLoadChampionImages():

    @pytest.mark.asyncio
    async def test_every_image_comes_from_cdragon(self, veigar):
        champion, raw = veigar
        session = FakeSession({"": ICON})

        failures = await images.load_champion_images(session, champion, raw, "16.23")

        assert failures == []
        assert champion.image.full.startswith("veigar.") and champion.image.group == "champion"
        assert champion.q.image.full.startswith("veigarbalefulstrike.") and champion.q.image.group == "spell"
        assert champion.r.image.full.startswith("veigarprimordialburst.")
        assert champion.passive.image.full.startswith("veigar_entropy.") and champion.passive.image.group == "passive"
        assert "champion-icons/45.png" in session.urls[0]


    @pytest.mark.asyncio
    async def test_a_missing_image_keeps_the_old_one_and_is_reported(self, veigar):
        champion, raw = veigar
        session = FakeSession({"champion-icons": ICON, "veigardarkmatter": ICON, "veigareventhorizon": ICON,
                               "veigarprimordialburst": ICON, "veigar_entropy": ICON, "splash": ICON})

        failures = await images.load_champion_images(session, champion, raw, "16.23")

        assert champion.q.image.full == "VeigarBalefulStrike.png"  # Data Dragon's
        assert champion.w.image.full.startswith("veigardarkmatter.")
        assert failures == [f"spell veigarbalefulstrike: 404 Image not found — {STRIKE_URL}"]


    @pytest.mark.asyncio
    async def test_a_spell_without_icon_is_reported(self, veigar):
        champion, raw = veigar
        del raw.cdragon["Characters/Veigar/Spells/VeigarBalefulStrikeAbility/VeigarBalefulStrike"]["mSpell"]["mImgIconName"]

        failures = await images.load_champion_images(FakeSession({"": ICON}), champion, raw, "16.23")

        assert failures == ["q: no icon in the spell data"]


class TestChampionIcons():

    @pytest.mark.asyncio
    async def test_every_icon_of_the_champions_own_folder_is_kept_by_name(self, nidalee):
        champion, raw = nidalee
        session = FakeSession({"": ICON})

        failures = await images.load_champion_images(session, champion, raw, "16.23")

        assert failures == []
        assert set(champion.icons) == {"nidalee_q1", "nidalee_q2", "nidalee_w1", "nidalee_w2", "nidalee_e1",
                                       "nidalee_e2", "nidalee_r1", "nidalee_r2", "nidalee_passive",
                                       "nidalee_ontheprowl"}
        assert champion.icons["nidalee_passive"] == champion.passive.image  # the passive's group, not "spell"
        assert len(session.urls) == len(set(session.urls))  # a slot's icon downloads once


    @pytest.mark.asyncio
    async def test_extra_abilities_show_the_icon_they_name(self, nidalee):
        champion, raw = nidalee

        await images.load_champion_images(FakeSession({"": ICON}), champion, raw, "16.23")

        takedown, pounce, swipe = champion.extra_abilities
        assert takedown.image == champion.icons["nidalee_q2"]
        assert pounce.image.full.startswith("nidalee_w2.") and swipe.image.full.startswith("nidalee_e2.")


    @pytest.mark.asyncio
    async def test_an_unknown_icon_key_is_reported(self, nidalee):
        champion, raw = nidalee
        champion.extra_abilities[0].icon = "nidalee_q3"
        champion.q.stages[0].icon = "nidalee_q9"

        failures = await images.load_champion_images(FakeSession({"": ICON}), champion, raw, "16.23")

        assert champion.extra_abilities[0].image.full == "RivenTriCleave.png"  # keeps the old one
        assert failures == ["Takedown: icon 'nidalee_q3' is not in the champion's icons",
                            "Javelin Toss stage 1: icon 'nidalee_q9' is not in the champion's icons"]


    def test_skin_variants_are_left_out(self, veigar):
        _, raw = veigar
        raw.cdragon["Characters/Veigar/Spells/Skins"] = {"mSpell": {"mImgIconName": [
            "ASSETS/Characters/Veigar/HUD/Icons2D/Veigar_Passive_Skin09.dds",
            "ASSETS/Characters/Veigar/HUD/Icons2D/VeigarStoneSkin.dds"]}}

        assets = [asset.lower() for asset in images.own_icons(raw)]

        assert not any("_skin09" in asset for asset in assets)
        assert any("veigarstoneskin" in asset for asset in assets)  # a name like Wukong's passive stays


    def test_borrowed_icons_of_other_folders_are_left_out(self, veigar):
        _, raw = veigar
        raw.cdragon["Characters/Veigar/Spells/Borrowed"] = {
            "mSpell": {"mImgIconName": ["ASSETS/Characters/Ezreal/HUD/Icons2D/Ezreal_TrueshotBarrage.dds"]}}

        assert not any("ezreal" in asset.lower() for asset in images.own_icons(raw))


class TestSplash():

    @pytest.mark.asyncio
    async def test_the_base_skins_splash_comes_from_the_client_files(self, veigar):
        champion, raw = veigar
        session = FakeSession({"": ICON})

        failures = await images.load_champion_images(session, champion, raw, "16.23")

        assert failures == []
        assert (champion.splash.group, champion.splash.full) == ("splash", f"veigar.{images.pixel_hash(ICON)}.jpg")
        assert "https://raw.communitydragon.org/16.23/plugins/rcp-be-lol-game-data/global/default/v1/champions/45.json" in session.urls
        assert ("https://raw.communitydragon.org/16.23/plugins/rcp-be-lol-game-data/global/default/assets/characters/"
                "veigar/skins/base/images/veigar_splash_centered_0.jpg") in session.urls


    @pytest.mark.asyncio
    async def test_a_missing_champion_file_keeps_the_old_splash(self, veigar):
        champion, raw = veigar
        champion.splash = Image(full="veigar.old.jpg", group="splash")

        failures = await images.load_champion_images(FakeSession({"": ICON}, json=""), champion, raw, "16.23")

        assert champion.splash.full == "veigar.old.jpg"
        assert failures == ["splash: no base skin splash — https://raw.communitydragon.org/16.23/plugins/"
                            "rcp-be-lol-game-data/global/default/v1/champions/45.json"]


class TestRuneTreeIcons():

    @pytest.mark.asyncio
    async def test_each_tree_gets_its_icon_on_the_patch(self):
        patch = NewPatch(patch="16.23.1")
        session = FakeSession({"7200_domination": ICON})

        failures = await images.load_rune_tree_icons(
            session, patch, {8100: ("Domination", "assets/perks/styles/7200_domination.tex")}, "16.23")

        assert failures == []
        assert patch.rune_trees[8100].name == "Domination"
        assert patch.rune_trees[8100].image.full.startswith("7200_domination.") and patch.rune_trees[8100].image.group == "rune"
        assert session.urls == ["https://raw.communitydragon.org/16.23/game/assets/perks/styles/7200_domination.png"]


    @pytest.mark.asyncio
    async def test_a_missing_icon_leaves_the_tree_out(self):
        patch = NewPatch(patch="16.23.1")

        failures = await images.load_rune_tree_icons(
            FakeSession({}), patch, {8100: ("Domination", "assets/perks/styles/7200_domination.tex"), 8000: ("Precision", "")},
            "16.23")

        assert patch.rune_trees == {}
        assert failures[0].startswith("rune 7200_domination: 404 Image not found")
        assert failures[1] == "Precision: no icon in the tree data"


class TestLoadItemImage():

    @pytest.mark.asyncio
    async def test_the_icon_comes_from_cdragon(self):
        item = build_item(item_raw(GUNBLADE), item_entry(GUNBLADE))
        session = FakeSession({"": ICON})

        failures = await images.load_item_image(session, item, item_raw(GUNBLADE), "16.23")

        assert failures == []
        assert item.image.full.startswith("3146_hextechgunblade.") and item.image.group == "item"
        assert session.urls == ["https://raw.communitydragon.org/16.23/game/assets/items/icons2d/3146_hextechgunblade.png"]


    @pytest.mark.asyncio
    async def test_a_missing_image_keeps_data_dragons(self):
        item = build_item(item_raw(GUNBLADE), item_entry(GUNBLADE))

        failures = await images.load_item_image(FakeSession({}), item, item_raw(GUNBLADE), "16.23")

        assert item.image.full == "3146.png"
        assert failures[0].startswith("404 Image not found")


class TestMasterworkBorder():

    @pytest.mark.asyncio
    async def test_ornns_overlay_is_stored_on_the_patch(self):
        patch = NewPatch(patch="16.23.1")
        session = FakeSession({"bordertreatmentornn": ICON})

        failures = await images.load_masterwork_border(session, patch, fixture("items.bin.json"), "16.23")

        assert failures == []
        assert patch.masterwork_border.full.startswith("bordertreatmentornn.") and patch.masterwork_border.group == "item"
        assert session.urls == ["https://raw.communitydragon.org/16.23/game/assets/items/itemmodifiers/bordertreatmentornn.png"]


    @pytest.mark.asyncio
    async def test_a_missing_modifier_is_reported(self):
        patch = NewPatch(patch="16.23.1")

        failures = await images.load_masterwork_border(FakeSession({}), patch, {}, "16.23")

        assert patch.masterwork_border is None
        assert failures == ["no overlay in Items/ItemModifiers/OrnnItemsModifier"]
