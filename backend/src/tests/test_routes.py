import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.server.models.champion import Champion
from src.server.models.image import Image
from src.server.models.item import Item
from src.server.models.patch import Patch, RuneTree
from src.server.models.rune import Rune
from src.server.models.summonerspell import Summonerspell
from src.server.routes import champion, item, rune, summonerspell


# One entry per type: route module, prefix, fixture, model, the fetch and update function names in the module.
CASES = [
    (champion, "champion", "test_group/champions/riven.json", Champion, "fetch_champion_by_id", "update_champion"),
    (item, "item", "test_group/items/sheen.json", Item, "fetch_item_by_id", "update_item"),
    (rune, "rune", "test_group/runes/conqueror.json", Rune, "fetch_rune_by_id", "update_rune"),
    (summonerspell, "summonerspell", "test_group/summonerspells/ignite.json", Summonerspell,
     "fetch_summonerspell_by_id", "update_summonerspell"),
]


def load(path: str) -> dict:
    with open(f"src/tests/static/{path}", encoding="utf-8") as file:
        return json.load(file)


def request(module, prefix: str, method: str, url: str, **kwargs):
    # Starlette's TestClient doesn't work with this httpx version, so the ASGI transport is used directly.
    app = FastAPI()
    app.include_router(module.router, prefix=f"/{prefix}")
    app.include_router(module.admin, prefix=f"/admin/{prefix}")

    async def send():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, url, **kwargs)
    return asyncio.run(send())


@pytest.mark.parametrize("module, prefix, path, model, fetch, _", CASES)
def test_get_returns_the_document_with_id(monkeypatch, module, prefix, path, model, fetch, _):
    document = model.parse_obj(load(path))
    monkeypatch.setattr("src.server.routes.helpers." + fetch, AsyncMock(return_value=document))

    response = request(module, prefix, "GET", f"/{prefix}/{document.id}")

    assert response.status_code == 200
    assert model.parse_obj(response.json()) == document
    assert response.json()["_id"] == document.id


@pytest.mark.parametrize("module, prefix, path, model, _, update", CASES)
def test_put_parses_the_body_and_saves_it(monkeypatch, module, prefix, path, model, _, update):
    body = load(path)
    saved = AsyncMock(return_value=SimpleNamespace(matched_count=1, modified_count=1))
    monkeypatch.setattr(f"{module.__name__}.{update}", saved)

    response = request(module, prefix, "PUT", f"/admin/{prefix}/", json=body)

    assert response.status_code == 200
    assert saved.await_args.args[0] == model.parse_obj(body)


@pytest.mark.parametrize("module, prefix, path, model, _, update", CASES)
def test_put_rejects_an_invalid_body(monkeypatch, module, prefix, path, model, _, update):
    monkeypatch.setattr(f"{module.__name__}.{update}", AsyncMock())

    response = request(module, prefix, "PUT", f"/admin/{prefix}/", json={"name": "only a name"})

    assert response.status_code == 422


class TestRuneTrees():

    def test_the_patchs_own_trees(self, monkeypatch):
        tree = RuneTree(name="Domination", image=Image(full="7200_domination.1a2b3c4d.png", group="rune"))
        patch = Patch(_id="0123456789abcdef01234567", patch="16.23.1", rune_trees={8100: tree})
        monkeypatch.setattr(rune, "fetch_patch_by_name", AsyncMock(return_value=patch))

        response = request(rune, "rune", "GET", "/rune/trees/16.23.1")

        assert response.json() == {"8100": tree.dict()}


    def test_an_unknown_patch_is_a_404(self, monkeypatch):
        monkeypatch.setattr(rune, "fetch_patch_by_name", AsyncMock(return_value=None))

        assert request(rune, "rune", "GET", "/rune/trees/1.1.1").status_code == 404
