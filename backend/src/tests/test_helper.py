import aiohttp
import asyncio
import pytest

from datetime import datetime
from unittest.mock import Mock

from src.server.loader import helper
from src.server.loader.helper import (
    SafeSession,
    info_loader,
    patch_sort_key,
    riot_to_wiki_patch,
    wiki_to_riot_patch,
    wiki_release_to_datetime,
    wiki_to_datetime
)
from src.server.loader.patchexceptions import PatcherError, ScrapeError






def test_info_loader():
    assert set(info_loader().wikiNames) == {"champions", "items", "runes", "summonerspells"}



def test_patch_sort_key():
    patches = ["15.10.1", "15.9.1", "14.24.1", "15.1.1"]
    assert sorted(patches, key=patch_sort_key) == ["14.24.1", "15.1.1", "15.9.1", "15.10.1"]


@pytest.mark.parametrize(
    "riot_patch, expected_wiki_patch", [
        ("15.7.1", "V25.07"),
        ("15.10.2", "V25.10")
    ],
)
def test_riot_to_wiki_patch(riot_patch, expected_wiki_patch):
    result = riot_to_wiki_patch(riot_patch)
    assert result == expected_wiki_patch

@pytest.mark.parametrize(
    "invalid_patch", [
        ("15."), ("abc.2.1"), ("15.abc.1"), (""), (15)
    ]
)
def test_riot_to_wiki_patch_invalid_format(invalid_patch):
    with pytest.raises(PatcherError):
        riot_to_wiki_patch(invalid_patch)


@pytest.mark.parametrize(
    "wiki_patch, expected_riot_patch", [
        ("V25.07", "15.7.1"),
        ("v14.10", "14.10.1"),
        ("V25.S1.3", "15.3.1")
    ],
)
def test_wiki_to_riot_patch(wiki_patch, expected_riot_patch):
    result = wiki_to_riot_patch(wiki_patch)
    assert result == expected_riot_patch

@pytest.mark.parametrize(
    "invalid_patch", [
        ("25.07"),       # Missing 'V'
        ("V25"),         # Missing minor version
        ("V25.abc"),     # Invalid minor version
        ("V"),           # Totally broken
        (""),            # Empty
        (25),            # Not a string
    ]
)
def test_wiki_to_riot_patch_invalid_format(invalid_patch):
    with pytest.raises(PatcherError):
        wiki_to_riot_patch(invalid_patch)




@pytest.mark.parametrize(
    "wiki_release, expected", [
        ("March 19th, 2025", datetime(2025, 3, 19)),
        ("August 1st, 2024", datetime(2024, 8, 1)),
    ]
)
def test_wiki_release_to_datetime(wiki_release, expected):
    assert wiki_release_to_datetime(wiki_release) == expected


@pytest.mark.parametrize(
    "wiki_hotfix, release_date, expected", [
        ("March 20th Hotfix", datetime(2025, 3, 19), datetime(2025, 3, 20)),
        ("August 22nd Hotfix", datetime(2024, 8, 14), datetime(2024, 8, 22)),
        ("January 3rd Hotfix", datetime(2024, 12, 11), datetime(2025, 1, 3)),
    ]
)
def test_wiki_to_datetime(wiki_hotfix, release_date, expected):
    assert wiki_to_datetime(wiki_hotfix, release_date) == expected


@pytest.mark.parametrize(
    "invalid_date", [("Hotfix"), ("Smarch 3rd Hotfix"), ("March Hotfix")]
)
def test_wiki_to_datetime_invalid(invalid_date):
    with pytest.raises(ScrapeError):
        wiki_to_datetime(invalid_date, datetime(2025, 3, 19))



class FailingSession:
    def __init__(self, *errors):
        self.errors = list(errors)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        error = self.errors.pop(0) if self.errors else None
        return FakeResponse(error)


class FakeResponse:
    def __init__(self, error):
        self.error = error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    async def json(self):
        return {"ok": True}


def http_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=None, history=(), status=status)


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(helper, "patch_logger", Mock())
    monkeypatch.setattr(helper, "load_logger", Mock())
    return sleeps


@pytest.mark.parametrize("error", [aiohttp.ServerDisconnectedError(), asyncio.TimeoutError(), http_error(503)])
async def test_retry_repeats_network_errors(no_sleep, error):
    session = FailingSession(error)

    assert await SafeSession(session).get_json("url") == {"ok": True}
    assert session.calls == 2


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), http_error(503), http_error(429)])
async def test_retry_gives_up_after_max_retries_without_a_last_wait(no_sleep, error):
    session = FailingSession(*[error] * 3)

    with pytest.raises(RuntimeError, match="Max retry"):
        await SafeSession(session, backoff_factor=25).get_json("url")
    assert session.calls == 3
    assert no_sleep == [25, 50]


@pytest.mark.parametrize("error", [KeyError("bug"), http_error(400)])
async def test_retry_lets_other_errors_through(no_sleep, error):
    session = FailingSession(error)

    with pytest.raises(type(error)):
        await SafeSession(session).get_json("url")
    assert session.calls == 1


async def test_retry_returns_empty_on_404(no_sleep):
    assert await SafeSession(FailingSession(http_error(404))).get_json("url") == ""


async def test_a_backoff_holds_every_request_of_the_session():
    session = SafeSession(FailingSession())
    session.backoff_event.clear()  # another request got a 429 and waits it out
    request = asyncio.create_task(session.get_json("url"))
    await asyncio.sleep(0)

    assert session.session.calls == 0
    session.backoff_event.set()
    assert await request == {"ok": True}


async def test_after_an_abort_no_request_starts():
    session = SafeSession(FailingSession())
    session.abort_event.set()

    with pytest.raises(RuntimeError, match="aborted"):
        await session.get_json("url")
    assert session.session.calls == 0
