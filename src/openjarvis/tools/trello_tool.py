"""Trello tool — let Jarvis read and update the user's Trello boards by voice.

Uses the Trello REST API with a personal API key + token, read from the
environment:

* ``TRELLO_API_KEY``  — from https://trello.com/power-ups/admin
* ``TRELLO_TOKEN``    — generated from the same page ("Token" link)
* ``TRELLO_DEFAULT_BOARD`` (optional) — board used when none is named

Boards, lists and cards are matched by (accent-insensitive) name so the user
can say "mueve la tarjeta del switch a En curso" without IDs.
"""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

API = "https://api.trello.com/1"
_ACTIONS = (
    "boards",
    "board_summary",
    "my_cards",
    "due_soon",
    "search",
    "create_card",
    "move_card",
    "comment",
    "complete_card",
)
_WRITE_ACTIONS = {"create_card", "move_card", "comment", "complete_card"}


class TrelloError(RuntimeError):
    """A user-facing Trello problem (missing keys, unknown board, ...)."""


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w\s]", " ", plain).split())


def best_match(query: str, items: List[Dict[str, Any]], key: str = "name") -> Any:
    """Return the item whose name best matches *query*, or None.

    Exact match beats prefix, prefix beats "all words contained".
    """
    q = _norm(query)
    if not q:
        return None
    exact, prefix, contains = [], [], []
    q_words = q.split()
    for item in items:
        name = _norm(item.get(key, ""))
        if name == q:
            exact.append(item)
        elif name.startswith(q):
            prefix.append(item)
        elif all(w in name for w in q_words):
            contains.append(item)
    for bucket in (exact, prefix, contains):
        if bucket:
            return min(bucket, key=lambda it: len(it.get(key, "")))
    return None


def _parse_due(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_due(value: Optional[str]) -> str:
    due = _parse_due(value)
    if due is None:
        return ""
    local = due.astimezone()
    return local.strftime("%d/%m %H:%M")


class TrelloClient:
    """Minimal Trello REST client (httpx)."""

    def __init__(
        self,
        api_key: str = "",
        token: str = "",
        http: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("TRELLO_API_KEY", "")
        self.token = token or os.environ.get("TRELLO_TOKEN", "")
        self._http = http or httpx.request

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.token)

    def call(self, method: str, path: str, **params: Any) -> Any:
        if not self.configured:
            raise TrelloError(
                "Trello no está configurado: faltan TRELLO_API_KEY y TRELLO_TOKEN. "
                "Corre scripts\\windows\\configurar-trello.ps1."
            )
        query = {"key": self.api_key, "token": self.token}
        query.update({k: v for k, v in params.items() if v is not None})
        resp = self._http(method, f"{API}{path}", params=query, timeout=20.0)
        if resp.status_code == 401:
            raise TrelloError(
                "Trello rechazó la clave o el token (401). Vuelve a configurarlos."
            )
        if resp.status_code >= 400:
            raise TrelloError(f"Trello respondió {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    # -- lookups ---------------------------------------------------------

    def boards(self) -> List[Dict[str, Any]]:
        return self.call(
            "GET", "/members/me/boards", filter="open", fields="name,url,shortUrl"
        )

    def board(self, name: Optional[str]) -> Dict[str, Any]:
        boards = self.boards()
        wanted = name or os.environ.get("TRELLO_DEFAULT_BOARD", "")
        if not wanted:
            if len(boards) == 1:
                return boards[0]
            names = ", ".join(b["name"] for b in boards)
            raise TrelloError(f"¿En qué tablero? Tus tableros son: {names}.")
        found = best_match(wanted, boards)
        if found is None:
            names = ", ".join(b["name"] for b in boards)
            raise TrelloError(f"No encontré el tablero '{wanted}'. Tienes: {names}.")
        return found

    def lists_with_cards(self, board_id: str) -> List[Dict[str, Any]]:
        return self.call(
            "GET",
            f"/boards/{board_id}/lists",
            filter="open",
            cards="open",
            card_fields="name,due,dueComplete,shortUrl,idList,idMembers",
        )

    def find_list(self, board_id: str, name: str) -> Dict[str, Any]:
        lists = self.call("GET", f"/boards/{board_id}/lists", filter="open")
        found = best_match(name, lists)
        if found is None:
            names = ", ".join(lst["name"] for lst in lists)
            raise TrelloError(f"No encontré la lista '{name}'. Listas: {names}.")
        return found

    def find_card(self, name: str, board_name: Optional[str]) -> Dict[str, Any]:
        if board_name or os.environ.get("TRELLO_DEFAULT_BOARD"):
            board = self.board(board_name)
            cards = self.call(
                "GET",
                f"/boards/{board['id']}/cards",
                filter="open",
                fields="name,shortUrl,idList,due,dueComplete",
            )
            found = best_match(name, cards)
            if found is not None:
                return found
        result = self.call(
            "GET",
            "/search",
            query=name,
            modelTypes="cards",
            cards_limit=10,
            card_fields="name,shortUrl,idList,idBoard,due,dueComplete",
            partial="true",
        )
        found = best_match(name, result.get("cards", []))
        if found is None:
            raise TrelloError(f"No encontré ninguna tarjeta llamada '{name}'.")
        return found


@ToolRegistry.register("trello")
class TrelloTool(BaseTool):
    """Read and update Trello boards, lists and cards."""

    tool_id = "trello"
    is_local = False

    def __init__(self, client: Optional[TrelloClient] = None) -> None:
        self._client = client or TrelloClient()

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="trello",
            description=(
                "Work with the user's Trello boards. Read actions: 'boards' (list "
                "boards), 'board_summary' (lists and their cards of one board), "
                "'my_cards' (cards assigned to the user), 'due_soon' (cards due "
                "in the next N days or overdue), 'search' (find cards). Write "
                "actions — ALWAYS confirm with the user first: 'create_card', "
                "'move_card', 'comment', 'complete_card'. Boards, lists and cards "
                "are matched by name; IDs are not needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(_ACTIONS)},
                    "board": {
                        "type": "string",
                        "description": "Board name (optional if a default is set).",
                    },
                    "list": {
                        "type": "string",
                        "description": "List name, e.g. 'Backlog', 'En curso', "
                        "'Hecho' (create_card / move_card).",
                    },
                    "card": {
                        "type": "string",
                        "description": "Card name or part of it "
                        "(move_card / comment / complete_card).",
                    },
                    "name": {
                        "type": "string",
                        "description": "Title of the new card (create_card).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Card description (create_card).",
                    },
                    "due": {
                        "type": "string",
                        "description": "Due date ISO 8601 with timezone, "
                        "e.g. 2026-11-05T09:00:00-05:00 (create_card).",
                    },
                    "text": {"type": "string", "description": "Comment text."},
                    "query": {"type": "string", "description": "Search text."},
                    "days": {
                        "type": "integer",
                        "description": "Window for due_soon (default 7).",
                        "minimum": 1,
                        "maximum": 60,
                    },
                },
                "required": ["action"],
            },
            category="productivity",
            latency_estimate=1.5,
            timeout_seconds=30.0,
        )

    # -- actions -----------------------------------------------------------

    def _boards(self, **_: Any) -> str:
        boards = self._client.boards()
        if not boards:
            return "No tienes tableros abiertos en Trello."
        return "Tus tableros: " + "; ".join(b["name"].strip() for b in boards) + "."

    def _board_summary(self, board: Optional[str] = None, **_: Any) -> str:
        b = self._client.board(board)
        lists = self._client.lists_with_cards(b["id"])
        lines = [f"Tablero {b['name'].strip()} ({b.get('shortUrl') or b.get('url')}):"]
        for lst in lists:
            cards = lst.get("cards", [])
            names = ", ".join(c["name"] for c in cards[:8])
            more = f" y {len(cards) - 8} más" if len(cards) > 8 else ""
            lines.append(
                f"- {lst['name']} ({len(cards)}): {names}{more}"
                if cards
                else f"- {lst['name']}: vacía"
            )
        return "\n".join(lines)

    def _my_cards(self, **_: Any) -> str:
        cards = self._client.call(
            "GET",
            "/members/me/cards",
            filter="open",
            fields="name,due,dueComplete,shortUrl",
        )
        if not cards:
            return "No tienes tarjetas asignadas."
        parts = []
        for c in cards[:20]:
            due = _fmt_due(c.get("due"))
            parts.append(c["name"] + (f" (vence {due})" if due else ""))
        return f"Tienes {len(cards)} tarjetas asignadas: " + "; ".join(parts) + "."

    def _due_soon(self, board: Optional[str] = None, days: Any = 7, **_: Any) -> str:
        try:
            window = max(1, min(60, int(days)))
        except (TypeError, ValueError):
            window = 7
        if board or os.environ.get("TRELLO_DEFAULT_BOARD"):
            b = self._client.board(board)
            cards = self._client.call(
                "GET",
                f"/boards/{b['id']}/cards",
                filter="open",
                fields="name,due,dueComplete,shortUrl",
            )
        else:
            cards = self._client.call(
                "GET",
                "/members/me/cards",
                filter="open",
                fields="name,due,dueComplete,shortUrl",
            )
        now = datetime.now(timezone.utc)
        limit = now + timedelta(days=window)
        overdue, upcoming = [], []
        for c in cards:
            due = _parse_due(c.get("due"))
            if due is None or c.get("dueComplete"):
                continue
            if due < now:
                overdue.append((due, c))
            elif due <= limit:
                upcoming.append((due, c))
        if not overdue and not upcoming:
            return (
                f"No hay tarjetas vencidas ni que venzan en los próximos {window} días."
            )
        out = []
        if overdue:
            out.append(
                "Vencidas: "
                + "; ".join(
                    f"{c['name']} ({_fmt_due(c['due'])})"
                    for _, c in sorted(overdue, key=lambda x: x[0])
                )
                + "."
            )
        if upcoming:
            out.append(
                f"Vencen en {window} días: "
                + "; ".join(
                    f"{c['name']} ({_fmt_due(c['due'])})"
                    for _, c in sorted(upcoming, key=lambda x: x[0])
                )
                + "."
            )
        return " ".join(out)

    def _search(self, query: str = "", **_: Any) -> str:
        if not query:
            raise TrelloError("Dime qué buscar en Trello.")
        result = self._client.call(
            "GET",
            "/search",
            query=query,
            modelTypes="cards",
            cards_limit=10,
            card_fields="name,shortUrl,due",
            partial="true",
        )
        cards = result.get("cards", [])
        if not cards:
            return f"No encontré tarjetas con '{query}'."
        return "Encontré: " + "; ".join(c["name"] for c in cards) + "."

    def _create_card(
        self,
        board: Optional[str] = None,
        list: Optional[str] = None,  # noqa: A002 (tool parameter name)
        name: str = "",
        description: Optional[str] = None,
        due: Optional[str] = None,
        **_: Any,
    ) -> str:
        if not name:
            raise TrelloError("Falta el título de la tarjeta.")
        b = self._client.board(board)
        lst = self._client.find_list(b["id"], list or "Backlog")
        card = self._client.call(
            "POST",
            "/cards",
            idList=lst["id"],
            name=name,
            desc=description,
            due=due,
            pos="top",
        )
        return (
            f"Creé la tarjeta '{card['name']}' en {lst['name']} "
            f"({b['name'].strip()}): {card.get('shortUrl', '')}"
        )

    def _move_card(
        self,
        card: str = "",
        list: Optional[str] = None,  # noqa: A002
        board: Optional[str] = None,
        **_: Any,
    ) -> str:
        if not card or not list:
            raise TrelloError("Necesito el nombre de la tarjeta y la lista de destino.")
        c = self._client.find_card(card, board)
        board_id = c.get("idBoard") or self._client.board(board)["id"]
        lst = self._client.find_list(board_id, list)
        self._client.call("PUT", f"/cards/{c['id']}", idList=lst["id"], pos="top")
        return f"Moví '{c['name']}' a {lst['name']}."

    def _comment(
        self, card: str = "", text: str = "", board: Optional[str] = None, **_: Any
    ) -> str:
        if not card or not text:
            raise TrelloError("Necesito la tarjeta y el texto del comentario.")
        c = self._client.find_card(card, board)
        self._client.call("POST", f"/cards/{c['id']}/actions/comments", text=text)
        return f"Comenté en '{c['name']}'."

    def _complete_card(
        self, card: str = "", board: Optional[str] = None, **_: Any
    ) -> str:
        if not card:
            raise TrelloError("¿Qué tarjeta marco como completada?")
        c = self._client.find_card(card, board)
        self._client.call("PUT", f"/cards/{c['id']}", dueComplete="true")
        return f"Marqué '{c['name']}' como completada."

    def execute(self, **params: Any) -> ToolResult:
        params = dict(params)  # don't mutate the caller's dict
        action = str(params.pop("action", "")).strip()
        handler = getattr(self, f"_{action}", None) if action in _ACTIONS else None
        if handler is None:
            return ToolResult(
                tool_name="trello",
                content=f"Acción desconocida: {action!r}. Usa una de {list(_ACTIONS)}.",
                success=False,
            )
        try:
            content = handler(**params)
        except TrelloError as exc:
            return ToolResult(tool_name="trello", content=str(exc), success=False)
        except httpx.HTTPError as exc:
            return ToolResult(
                tool_name="trello",
                content=f"No pude conectar con Trello: {exc}",
                success=False,
            )
        return ToolResult(
            tool_name="trello",
            content=content,
            success=True,
            metadata={"action": action, "write": action in _WRITE_ACTIONS},
        )


__all__ = ["TrelloClient", "TrelloError", "TrelloTool", "best_match"]
