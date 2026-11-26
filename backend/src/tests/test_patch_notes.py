from datetime import datetime

import pytest

from src.server.loader.patch_notes import (hotfix_dates, hotfix_notes, notes_with_hotfixes, page_text, parse_patch_notes,
                                           wikitext_to_text)
from src.server.models.change import patch_note


@pytest.fixture
def load_wikitext():
    def load(name: str) -> str:
        with open(f"src/tests/static/wikitext/{name}.txt", encoding="utf-8") as file:
            return file.read()
    return load


@pytest.fixture
def notes_26_21(load_wikitext):
    return parse_patch_notes(load_wikitext("V26.21"))


def texts(changes):
    return [change.text for change in changes]


@pytest.mark.parametrize("wikitext, text", [
    ("Cooldown reduced to {{ap|9 to 4}} seconds from {{ap|9 to 5}}.", "Cooldown reduced to 9 to 4 seconds from 9 to 5."),
    ("{{ap|150 to 550 3}}", "150 to 550"),
    ("{{ap|53.33 to 240|round=2}}", "53.33 to 240"),
    ("{{ap|10|20|30}}", "10 / 20 / 30"),
    ("{{as|{{pp|key=%|60 to 80 for 3|1 to 13}} AD}}", "60% to 80% (based on level) AD"),
    ("{{pp|0 to 50 for 11|key=%|type=[[File:Varus Piercing Arrow.png|20px|border]] ''Piercing Arrow's'' charge time}}",
     "0% to 50% (based on Piercing Arrow's charge time)"),
    ("{{as|120% '''bonus''' AD}} from {{as|80%|AD}}", "120% bonus AD from 80%"),
    ("{{rd|40|20}}", "40 (melee) / 20 (ranged)"),
    ("{{sbc|Bug Fix:}} Reveals {{tip|untargetable}} and {{tip|death|lethal}}", "Bug Fix: Reveals untargetable and lethal"),
    ("{{ai|Captive Audience|Jhin|Lotus Trap}} and {{iis|Sheen}} and {{sis|Flash}}", "Lotus Trap and Sheen's and Flash's"),
    ("[[Summoner's Rift|the Rift]] and [[Minion]]", "the Rift and Minion"),
    ("{{Anchor|January 9th Hotfix}}January 9th Hotfix<ref>X — [https://x.com/a b]</ref>", "January 9th Hotfix"),
    ("ARAM&colon; Mayhem", "ARAM: Mayhem"),
])
def test_wikitext_to_text(wikitext, text):
    assert wikitext_to_text(wikitext) == text


def test_champions_with_their_ability_lines(notes_26_21):
    champions = notes_26_21["champions"]

    assert len(champions["changed"]) == 29  # the same 29 the CDragon diff found for 16.21
    assert champions["changed"]["Darius"] == {"Decimate": [patch_note("Cooldown reduced to 9 to 4 seconds from 9 to 5.")]}
    assert texts(champions["changed"]["Jinx"]["Stats"]) == ["Base health reduced to 610 from 630.",
                                                      "Attack damage growth reduced to 3 from 3.25."]
    assert list(champions["changed"]["Lee Sin"]) == ["Safeguard", "Tempest", "Dragon's Rage"]


def test_third_level_lines_are_details_of_the_line_above(notes_26_21):
    sion = notes_26_21["champions"]["changed"]["Sion"]["Unstoppable Onslaught"]

    assert len(sion) == 4
    assert sion[1].text.startswith("Bonus AD modifier increased")
    assert sion[1].details == ["Maximum bonus AD ratio increased to 120% bonus AD from 80%."]
    assert sion[2].details == []


def test_item_sub_lines_are_details():
    notes = parse_patch_notes("=== Items ===\n;{{ii|Sheen}}\n* Spellblade changed\n** Damage increased\n* Cost reduced\n")

    assert notes["items"]["changed"]["Sheen"] == [patch_note("Spellblade changed", ["Damage increased"]),
                                                  patch_note("Cost reduced")]


def test_the_champion_name_is_the_template_parameter(notes_26_21):
    # The wiki names Nunu & Willump "Nunu"; matching it to Data Dragon is the name dictionary's job.
    assert "Nunu" in notes_26_21["champions"]["changed"]


def test_items_runes_and_summoner_spells(notes_26_21):
    assert notes_26_21["items"]["changed"]["Gluttonous Greaves"] == [
        patch_note("Total cost increased to 1100 from 1000.", ["Combine cost increased to 800 from 700."])]
    assert list(notes_26_21["runes"]["changed"]) == ["Hail of Blades"]
    assert list(notes_26_21["summonerspells"]["changed"]) == ["Teleport"]


def test_new_readded_and_removed_objects(load_wikitext):
    notes = parse_patch_notes(load_wikitext("V25.S1.1"))

    assert "Armored Advance" in notes["items"]["new"]
    assert "Aegis of the Legion" in notes["items"]["new"]  # re-added
    assert notes["items"]["deleted"] == ["Zephyr"]
    assert "Zombie Ward" in notes["runes"]["deleted"]
    assert "Armored Advance" not in notes["items"]["changed"]


def test_a_new_champion():
    notes = parse_patch_notes("=== Champions ===\n;{{ci|Zaahen}} - New champion\n* {{ai|Cultivation of War|Zaahen}} - Innate\n")

    assert notes["champions"]["new"] == ["Zaahen"]
    assert notes["champions"]["changed"] == {}


def test_a_line_without_deeper_lines_belongs_to_general():
    notes = parse_patch_notes("=== Champions ===\n;{{ci|Briar}}\n* {{sbc|Bug Fix:}} Fixed a bug.\n")

    assert notes["champions"]["changed"]["Briar"] == {"General": [patch_note("Bug Fix: Fixed a bug.")]}


def test_hotfix_dates(load_wikitext):
    assert hotfix_dates(load_wikitext("V26.21")) == [datetime(2026, 10, 22)]
    assert hotfix_dates(load_wikitext("V25.S1.1")) == [datetime(2025, 1, 9), datetime(2025, 1, 10),
                                                       datetime(2025, 1, 13), datetime(2025, 1, 22)]


def test_no_hotfixes():
    assert hotfix_dates("== League of Legends V26.22 ==\n=== Champions ===\n== See Also ==") == []


def test_a_hotfix_only_reads_its_own_section(load_wikitext):
    notes = parse_patch_notes(load_wikitext("V26.21"), datetime(2026, 10, 22))

    varus = notes["champions"]["changed"]["Varus"]
    assert list(notes["champions"]["changed"]) == ["Varus"]
    assert texts(varus["Living Vengeance"]) == [
        "Attack speed ratio for bonus AD and AP on kill increased to 14% bonus total attack speed from 11%.",
        "Attack speed ratio for bonus AD and AP on takedown increased to 42% bonus total attack speed from 33%."]
    assert texts(varus["Piercing Arrow"]) == ["Minimum base damage increased to 50 to 250 from 50 to 230."]
    assert notes["items"]["changed"] == {}


def test_a_hotfix_sorts_its_entries_by_template_and_skips_mode_changes(load_wikitext):
    notes = parse_patch_notes(load_wikitext("V25.S1.1"), datetime(2025, 1, 10))

    assert list(notes["items"]["changed"]) == ["Armored Advance", "Chainlaced Crushers", "Sorcerer's Shoes",
                                               "Spellslinger's Shoes", "Swiftmarch"]
    assert list(notes["summonerspells"]["changed"]) == ["Teleport"]
    assert notes["champions"]["changed"] == {}  # Swiftplay's champion changes are mode changes


def test_a_missing_hotfix_gives_no_notes(load_wikitext):
    notes = parse_patch_notes(load_wikitext("V26.21"), datetime(2026, 10, 30))

    assert all(not type_notes["changed"] for type_notes in notes.values())


def test_several_hotfixes_keep_the_lines_of_each():
    wikitext = ("|Release = January {{NumberSup|8}}, 2025\n== Hotfixes ==\n"
                "=== January 10th Hotfix ===\n;{{ii|Sheen}}\n* Damage increased.\n"
                ";{{ci|Briar}}\n* {{ai|Head Rush|Briar}}\n** Cooldown reduced.\n"
                "=== January 13th Hotfix ===\n;{{ii|Sheen}}\n* Cost reduced.\n"
                ";{{ci|Briar}}\n* {{ai|Head Rush|Briar}}\n** Damage increased.\n== See Also ==")

    notes = hotfix_notes(wikitext, [datetime(2025, 1, 13), datetime(2025, 1, 10)])

    assert texts(notes["items"]["changed"]["Sheen"]) == ["Damage increased.", "Cost reduced."]
    assert texts(notes["champions"]["changed"]["Briar"]["Head Rush"]) == ["Cooldown reduced.", "Damage increased."]


def test_a_patch_takes_the_hotfixes_already_on_the_wiki(load_wikitext):
    notes = notes_with_hotfixes(load_wikitext("V26.21"))

    assert texts(notes["champions"]["changed"]["Varus"]["Piercing Arrow"])[-1] == (
        "Minimum base damage increased to 50 to 250 from 50 to 230.")
    assert notes["champions"]["changed"].keys() > {"Varus"}  # the main part is still there


def test_no_hotfixes_give_empty_notes(load_wikitext):
    notes = hotfix_notes(load_wikitext("V26.21"), [])

    assert all(not type_notes["changed"] for type_notes in notes.values())


def test_page_text_of_a_missing_page():
    assert page_text({"query": {"pages": [{"title": "V99.01", "missing": True}]}}) is None
