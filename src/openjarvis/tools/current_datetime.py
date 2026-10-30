"""Current date/time tool — lets the agent know the local date and time."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_DAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _part_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "mañana"
    if 12 <= hour < 19:
        return "tarde"
    return "noche"


def describe_now(now: datetime | None = None) -> str:
    """Return the local date and time as a short Spanish + ISO description."""
    now = (now or datetime.now()).astimezone()
    tz = now.tzname() or ""
    offset = now.strftime("%z")
    offset_fmt = f"UTC{offset[:3]}:{offset[3:]}" if offset else ""
    return (
        f"Hoy es {_DAYS_ES[now.weekday()]} {now.day} de "
        f"{_MONTHS_ES[now.month - 1]} de {now.year}. "
        f"Son las {now.strftime('%H:%M')} ({_part_of_day(now.hour)}). "
        f"Zona horaria: {tz} {offset_fmt}".strip()
        + f". ISO: {now.isoformat(timespec='minutes')}"
    )


@ToolRegistry.register("current_datetime")
class CurrentDateTimeTool(BaseTool):
    """Return the local date, time, weekday and time zone of this computer."""

    tool_id = "current_datetime"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="current_datetime",
            description=(
                "Returns the current local date, time, weekday and time zone of "
                "the user's computer. Use it before greeting (good morning / "
                "afternoon / evening) and for any question about today, the "
                "time, or how long until a date."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="utility",
            cost_estimate=0.0,
            latency_estimate=0.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        return ToolResult(
            tool_name="current_datetime",
            content=describe_now(),
            success=True,
        )


__all__ = ["CurrentDateTimeTool", "describe_now"]
