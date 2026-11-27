import json
from datetime import datetime
from pathlib import Path

import pytest

import src.server.loader.images as images
from src.server.loader.champion_builder import build_champion
from src.server.loader.item_builder import build_item
from src.server.loader.patchexceptions import LoadError
from src.server.models.champion import RawChampion
from src.server.models.json_validation import ChampionJson
from src.server.models.patch import NewPatch
from src.tests.test_item_builder import GUNBLADE
from src.tests.test_item_builder import entry as item_entry
from src.tests.test_item_builder import raw as item_raw


CDRAGON = Path(__file__).parent / "static" / "cdragon"
STRIKE_URL = "https://raw.communitydragon.org/16.23/game/assets/characters/veigar/hud/icons2d/veigarbalefulstrike.png"


def fixture(name: str) -> dict:
    return json.loads((CDRAGON / name).read_text(encoding="utf-8"))


class FakeSession:
    """Answers like SafeSession: the bytes for known URLs, b"" for everything else (a 404)."""

    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def get_bytes(self, url: str) -> bytes:
        self.urls.append(url)
        return next((data for part, data in self.responses.items() if part in url), b"")


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(images, "IMAGE_DIR", tmp_path)
    return tmp_path


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
    async def test_name_carries_a_content_hash(self, image_dir):
        image = await images.store_image(FakeSession({"strike": b"icon"}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert (image.group, image.full) == ("spell", "veigarbalefulstrike.c2d4b446.png")  # sha256(b"icon")
        assert (image_dir / "spell" / image.full).read_bytes() == b"icon"


    @pytest.mark.asyncio
    async def test_same_image_same_file(self, image_dir):
        session = FakeSession({"strike": b"icon"})

        first = await images.store_image(session, STRIKE_URL, "spell", "veigarbalefulstrike")
        second = await images.store_image(session, STRIKE_URL, "spell", "veigarbalefulstrike")

        assert first == second
        assert len(list((image_dir / "spell").iterdir())) == 1


    @pytest.mark.asyncio
    async def test_changed_image_gets_a_new_file_and_the_old_one_stays(self, image_dir):
        old = await images.store_image(FakeSession({"strike": b"old"}), STRIKE_URL, "spell", "veigarbalefulstrike")
        new = await images.store_image(FakeSession({"strike": b"new"}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert old.full != new.full
        assert {path.name for path in (image_dir / "spell").iterdir()} == {old.full, new.full}


    @pytest.mark.asyncio
    async def test_missing_image_is_a_load_error_and_writes_nothing(self, image_dir):
        with pytest.raises(LoadError):
            await images.store_image(FakeSession({}), STRIKE_URL, "spell", "veigarbalefulstrike")

        assert not any(image_dir.iterdir())


class TestLoadChampionImages():

    @pytest.mark.asyncio
    async def test_every_image_comes_from_cdragon(self, veigar):
        champion, raw = veigar
        session = FakeSession({"": b"icon"})

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
        session = FakeSession({"champion-icons": b"icon", "veigardarkmatter": b"icon", "veigareventhorizon": b"icon",
                               "veigarprimordialburst": b"icon", "veigar_entropy": b"icon"})

        failures = await images.load_champion_images(session, champion, raw, "16.23")

        assert champion.q.image.full == "VeigarBalefulStrike.png"  # Data Dragon's
        assert champion.w.image.full.startswith("veigardarkmatter.")
        assert failures == [f"spell veigarbalefulstrike: 404 Image not found — {STRIKE_URL}"]


    @pytest.mark.asyncio
    async def test_a_spell_without_icon_is_reported(self, veigar):
        champion, raw = veigar
        del raw.cdragon["Characters/Veigar/Spells/VeigarBalefulStrikeAbility/VeigarBalefulStrike"]["mSpell"]["mImgIconName"]

        failures = await images.load_champion_images(FakeSession({"": b"icon"}), champion, raw, "16.23")

        assert failures == ["q: no icon in the spell data"]


class TestLoadItemImage():

    @pytest.mark.asyncio
    async def test_the_icon_comes_from_cdragon(self):
        item = build_item(item_raw(GUNBLADE), item_entry(GUNBLADE))
        session = FakeSession({"": b"icon"})

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
        session = FakeSession({"bordertreatmentornn": b"frame"})

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
