import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.server import errors
from src.server.models.rule import Rule
from src.server.routes import simulation


def send(app: FastAPI, method: str, url: str, **kwargs):
    async def run():
        # Without raise_app_exceptions=False the test would get the re-raised exception instead of the response.
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)
    return asyncio.run(run())


@pytest.fixture
def loggers(monkeypatch) -> dict[str, Mock]:
    mocks = {"sim": Mock(), "alert": Mock()}
    monkeypatch.setattr(errors, "sim_logger", mocks["sim"])
    monkeypatch.setattr(errors, "alert_logger", mocks["alert"])
    return mocks


@pytest.fixture
def simulate(monkeypatch, load_champion):
    def _simulate(combo: list[dict], attacker=None):
        champions = {"vayne": attacker or load_champion("vayne"), "darius": load_champion("darius")}
        monkeypatch.setattr(simulation, "get_required_champion", AsyncMock(side_effect=lambda id_: champions[id_]))
        app = FastAPI()
        errors.add_error_handlers(app)
        app.include_router(simulation.router, prefix="/simulation")
        rank = {"q": 1, "w": 1, "e": 1, "r": 1}
        body = {"id_attacker": "vayne", "lvl_attacker": 6, "ability_points_attacker": rank, "items_attacker": [],
                "id_defender": "darius", "lvl_defender": 6, "ability_points_defender": rank, "items_defender": [],
                "combo": combo}
        return send(app, "POST", "/simulation/v1", json=body)
    return _simulate


def action(slot: str) -> dict:
    return {"actor": "blue", "target": "red", "action_type": slot}


class TestSimulationRoute:
    def test_a_working_combo_is_unchanged(self, simulate, loggers):
        response = simulate([action("ba")])

        assert response.status_code == 200
        assert response.json()["damage"] > 0
        loggers["sim"].error.assert_not_called()

    def test_an_impossible_combo_is_a_client_error(self, simulate, loggers):
        response = simulate([action("ba"), action("i1")])

        body = response.json()
        assert response.status_code == 400
        assert body["code"] == "invalid_combo"
        assert "Vayne has nothing in slot i1" in body["detail"] and "action #1" in body["detail"]

    def test_broken_data_names_champion_and_rule(self, simulate, loggers, load_champion):
        vayne = load_champion("vayne")
        vayne.passive.rules.append(Rule.parse_obj({"trigger": "on_start", "delay": "1", "actions": [{"type_": "Damage", "props": {
            "target": "target", "scaling": "unknown_variable", "dmg_sub_type": "True"}}]}))

        body = simulate([action("ba")], attacker=vayne).json()

        assert body["code"] == "invalid_data"
        assert f"Vayne passive 'passive', rule {len(vayne.passive.rules)}" in body["detail"]

    def test_a_missing_ability_is_not_entered(self, simulate, loggers, load_champion):
        vayne = load_champion("vayne")
        vayne.q.stages = []

        response = simulate([action("q")], attacker=vayne)

        assert response.status_code == 501
        assert response.json()["code"] == "not_entered"
        assert "Vayne Q is not entered yet" in response.json()["detail"]

    def test_the_failed_request_is_logged_for_replaying(self, simulate, loggers):
        body = simulate([action("i1")]).json()

        message = loggers["sim"].error.call_args.args[0]
        assert body["error_id"] in message
        assert '"action_type": "i1"' in message and '"id_attacker": "vayne"' in message
        assert loggers["sim"].error.call_args.kwargs["exc_info"] is not None


class TestUnexpectedErrors:
    def test_any_route_error_gets_an_id_and_a_logged_traceback(self, loggers):
        app = FastAPI()
        errors.add_error_handlers(app)

        @app.get("/broken")
        async def broken():
            raise RuntimeError("database fell over")

        response = send(app, "GET", "/broken")

        body = response.json()
        assert response.status_code == 500
        assert body["code"] == "internal"
        assert body["error_id"] in loggers["alert"].error.call_args.args[0]
        assert isinstance(loggers["alert"].error.call_args.kwargs["exc_info"], RuntimeError)
