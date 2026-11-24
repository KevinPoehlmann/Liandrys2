import json
from pathlib import Path

import pytest

from src.server.loader.champion_source import (cdragon_version, champion_strings, fetch_build, fetch_wiki_templates,
                                               load_raw_champion)
from src.server.loader.patchexceptions import LoadError


CDRAGON = Path(__file__).parent / "static" / "cdragon"
BUILD = "16.23.8406595+branch.releases-16-23.content.release"


def fixture(name: str) -> dict:
    return json.loads((CDRAGON / name).read_text(encoding="utf-8"))


class FakeSession:
    """Answers like SafeSession: the JSON for known URLs, "" for everything else (a 404)."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def get_json(self, url: str) -> dict | str:
        self.urls.append(url)
        return next((data for part, data in self.responses.items() if part in url), "")


@pytest.fixture
def veigar_session():
    return FakeSession({
        "/16.23/content-metadata.json": {"version": BUILD},
        "/16.23/game/data/characters/veigar/veigar.bin.json": fixture("veigar.bin.json"),
        "gapprefix=Data+Veigar%2F": fixture("veigar.wiki.json"),
    })


def test_cdragon_folder_is_major_and_minor():
    assert cdragon_version("16.23.1") == "16.23"


async def test_build_number(veigar_session):
    assert await fetch_build(veigar_session, "16.23") == BUILD


def test_strings_keep_only_the_champions_spells():
    strings = fixture("veigar.strings.json")["entries"] | {
        "spell_annieq_tooltip": "Annie throws a fireball", "spell_veigarbalefulstrikex_name": "not a Veigar spell"}

    kept = champion_strings(strings, fixture("veigar.bin.json"))

    assert kept["spell_veigarbalefulstrike_tooltip"].startswith("Veigar unleashes a bolt of dark energy")
    assert "spell_annieq_tooltip" not in kept
    assert "spell_veigarbalefulstrikex_name" not in kept


async def test_wiki_templates_with_revision(veigar_session):
    templates = await fetch_wiki_templates(veigar_session, "Veigar")

    strike = templates["Template:Data Veigar/Baleful Strike"]
    assert strike.revision_id > 0
    assert "|damagetype   = Magic" in strike.text
    assert templates["Template:Data Veigar/Q"].text.startswith("#REDIRECT [[Template:Data Veigar/Baleful Strike]]")


async def test_raw_champion_keeps_everything(veigar_session):
    strings = fixture("veigar.strings.json")["entries"]

    raw = await load_raw_champion(veigar_session, "16.23.1", None, "Veigar", "Veigar", BUILD, strings)

    assert (raw.champion_id, raw.patch, raw.build) == ("Veigar", "16.23.1", BUILD)
    assert raw.cdragon == fixture("veigar.bin.json")
    assert raw.strings == strings
    assert len(raw.wiki) == 10


async def test_missing_champion_is_a_load_error():
    with pytest.raises(LoadError) as error:
        await load_raw_champion(FakeSession({}), "16.23.1", None, "Nobody", "Nobody", BUILD, {})

    assert error.value.code == 404
    assert error.value.url.endswith("/16.23/game/data/characters/nobody/nobody.bin.json")
