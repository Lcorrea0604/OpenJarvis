"""Tests for the Trello tool (HTTP layer faked, no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from openjarvis.tools.trello_tool import TrelloClient, TrelloTool, best_match

BOARDS = [
    {"id": "b1", "name": "GLOVESA · Infraestructura TI Integral", "shortUrl": "u1"},
    {"id": "b2", "name": "LEGALIS ", "shortUrl": "u2"},
]
LISTS = [
    {"id": "l1", "name": "Backlog"},
    {"id": "l2", "name": "En curso"},
    {"id": "l3", "name": "En revisión (Jefe)"},
    {"id": "l4", "name": "Hecho"},
]


def _iso(delta_days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=delta_days)).isoformat()


CARDS = [
    {
        "id": "c1",
        "name": "Cambiar switch del piso 2",
        "idList": "l1",
        "idBoard": "b1",
        "due": _iso(2),
        "dueComplete": False,
        "shortUrl": "s1",
    },
    {
        "id": "c2",
        "name": "Inventario de laptops",
        "idList": "l2",
        "idBoard": "b1",
        "due": _iso(-1),
        "dueComplete": False,
        "shortUrl": "s2",
    },
    {
        "id": "c3",
        "name": "Cableado almacén",
        "idList": "l4",
        "idBoard": "b1",
        "due": _iso(30),
        "dueComplete": False,
        "shortUrl": "s3",
    },
]


class FakeResponse:
    def __init__(self, data: Any, status: int = 200) -> None:
        self._data = data
        self.status_code = status
        self.text = str(data)

    def json(self) -> Any:
        return self._data


class FakeTrello:
    """Records calls and answers like the Trello REST API."""

    def __init__(self, status: int = 200) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.status = status

    def __call__(self, method, url, params=None, timeout=None):
        path = url.split("/1", 1)[1]
        self.calls.append((method, path, dict(params or {})))
        if self.status != 200:
            return FakeResponse("nope", self.status)
        if path == "/members/me/boards":
            return FakeResponse(BOARDS)
        if path.endswith("/lists"):
            if params.get("cards") == "open":
                return FakeResponse(
                    [
                        dict(lst, cards=[c for c in CARDS if c["idList"] == lst["id"]])
                        for lst in LISTS
                    ]
                )
            return FakeResponse(LISTS)
        if path.endswith("/cards") and method == "GET":
            return FakeResponse(CARDS)
        if path == "/members/me/cards":
            return FakeResponse(CARDS[:2])
        if path == "/search":
            q = params["query"].lower()
            return FakeResponse({"cards": [c for c in CARDS if q in c["name"].lower()]})
        if path == "/cards" and method == "POST":
            return FakeResponse({"id": "new", "name": params["name"], "shortUrl": "sn"})
        return FakeResponse({})


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.delenv("TRELLO_DEFAULT_BOARD", raising=False)
    return FakeTrello()


def _tool(fake: FakeTrello) -> TrelloTool:
    return TrelloTool(TrelloClient(api_key="k", token="t", http=fake))


def test_best_match():
    assert best_match("glovesa", BOARDS)["id"] == "b1"
    assert best_match("legalis", BOARDS)["id"] == "b2"
    assert best_match("en revision", LISTS)["id"] == "l3"
    assert best_match("hecho", LISTS)["id"] == "l4"
    assert best_match("nada que ver", LISTS) is None


def test_not_configured(monkeypatch):
    monkeypatch.delenv("TRELLO_API_KEY", raising=False)
    monkeypatch.delenv("TRELLO_TOKEN", raising=False)
    result = TrelloTool(TrelloClient()).execute(action="boards")
    assert not result.success
    assert "configurar-trello" in result.content


def test_unauthorized():
    result = _tool(FakeTrello(status=401)).execute(action="boards")
    assert not result.success
    assert "401" in result.content


def test_boards(fake):
    result = _tool(fake).execute(action="boards")
    assert result.success
    assert "GLOVESA" in result.content and "LEGALIS" in result.content
    assert fake.calls[0][2]["key"] == "k" and fake.calls[0][2]["token"] == "t"


def test_board_requires_name_when_several(fake):
    result = _tool(fake).execute(action="board_summary")
    assert not result.success
    assert "¿En qué tablero?" in result.content


def test_default_board_env(fake, monkeypatch):
    monkeypatch.setenv("TRELLO_DEFAULT_BOARD", "glovesa")
    result = _tool(fake).execute(action="board_summary")
    assert result.success
    assert "Backlog (1): Cambiar switch del piso 2" in result.content
    assert "En revisión (Jefe): vacía" in result.content


def test_due_soon_overdue_and_upcoming(fake):
    result = _tool(fake).execute(action="due_soon", board="glovesa", days=7)
    assert result.success
    assert "Vencidas: Inventario de laptops" in result.content
    assert "Cambiar switch del piso 2" in result.content
    assert "Cableado" not in result.content  # due in 30 days


def test_create_card_defaults_to_backlog(fake):
    result = _tool(fake).execute(
        action="create_card", board="glovesa", name="Revisar UPS sala de servidores"
    )
    assert result.success
    method, path, params = fake.calls[-1]
    assert (method, path) == ("POST", "/cards")
    assert params["idList"] == "l1"
    assert params["name"] == "Revisar UPS sala de servidores"
    assert "desc" not in params  # None values are not sent


def test_move_card_by_name(fake):
    result = _tool(fake).execute(
        action="move_card", board="glovesa", card="switch", list="en curso"
    )
    assert result.success, result.content
    method, path, params = fake.calls[-1]
    assert (method, path, params["idList"]) == ("PUT", "/cards/c1", "l2")


def test_move_card_unknown_list(fake):
    result = _tool(fake).execute(
        action="move_card", board="glovesa", card="switch", list="papelera"
    )
    assert not result.success
    assert "No encontré la lista" in result.content


def test_comment_and_complete(fake):
    tool = _tool(fake)
    assert tool.execute(
        action="comment", board="glovesa", card="inventario", text="Faltan 3 equipos"
    ).success
    assert fake.calls[-1][:2] == ("POST", "/cards/c2/actions/comments")
    assert tool.execute(
        action="complete_card", board="glovesa", card="inventario"
    ).success
    assert fake.calls[-1][2]["dueComplete"] == "true"


def test_search_without_board_uses_global_search(fake):
    result = _tool(fake).execute(action="search", query="cableado")
    assert result.success
    assert "Cableado almacén" in result.content


def test_unknown_action(fake):
    assert not _tool(fake).execute(action="borrar_todo").success
