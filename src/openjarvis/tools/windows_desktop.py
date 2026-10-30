"""Desktop tools for a voice assistant on Windows.

* ``open_app``       — open an installed app, a website or a known folder.
* ``system_status``  — battery, CPU, RAM, disk and uptime, in Spanish.
* ``media_control``  — volume and media keys (play/pause, next, previous).

They are deliberately *not* a shell: ``open_app`` only launches things the
user already has (Windows App Paths, Start-menu shortcuts, URLs and the
standard user folders), so a misheard voice command cannot run arbitrary
programs or delete anything. On non-Windows systems ``open_app`` falls back to
``xdg-open``/``open`` and ``media_control`` reports that it is unsupported.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import unicodedata
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower().strip())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    plain = re.sub(r"[^\w\s.:/-]", " ", plain)
    # Drop Spanish articles / filler a voice request tends to include.
    plain = re.sub(r"^(?:el|la|los|las|mi|mis|un|una|al|a)\s+", "", plain.strip())
    return " ".join(plain.split())


# Spoken name -> target understood by Windows ShellExecute (App Paths,
# System32 executables or protocol URIs).
WINDOWS_APPS: Dict[str, str] = {
    "calculadora": "calc",
    "bloc de notas": "notepad",
    "notas": "notepad",
    "paint": "mspaint",
    "explorador": "explorer",
    "explorador de archivos": "explorer",
    "archivos": "explorer",
    "configuracion": "ms-settings:",
    "ajustes": "ms-settings:",
    "wifi": "ms-settings:network-wifi",
    "bluetooth": "ms-settings:bluetooth",
    "sonido": "ms-settings:sound",
    "pantalla": "ms-settings:display",
    "actualizaciones": "ms-settings:windowsupdate",
    "administrador de tareas": "taskmgr",
    "terminal": "wt",
    "powershell": "powershell",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "navegador": "msedge",
    "firefox": "firefox",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "teams": "msteams:",
    "spotify": "spotify:",
    "whatsapp": "whatsapp:",
    "visual studio code": "code",
    "vs code": "code",
    "code": "code",
    "camara": "microsoft.windows.camera:",
    "reloj": "ms-clock:",
    "alarmas": "ms-clock:",
    "calendario": "outlookcal:",
    "correo": "outlookmail:",
    "tienda": "ms-windows-store:",
    "recortes": "ms-screenclip:",
}

WEBSITES: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "correo de google": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "drive": "https://drive.google.com",
    "calendario de google": "https://calendar.google.com",
    "google maps": "https://maps.google.com",
    "mapas": "https://maps.google.com",
    "whatsapp web": "https://web.whatsapp.com",
    "github": "https://github.com",
    "mi repositorio": "https://github.com/Lcorrea0604/OpenJarvis",
    "claude": "https://claude.ai",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com",
    "netflix": "https://www.netflix.com",
    "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "sunat": "https://www.sunat.gob.pe",
    "bcp": "https://www.viabcp.com",
    "interbank": "https://interbank.pe",
}

# Spoken folder name -> path relative to the user's home directory.
USER_FOLDERS: Dict[str, str] = {
    "descargas": "Downloads",
    "documentos": "Documents",
    "escritorio": "Desktop",
    "imagenes": "Pictures",
    "fotos": "Pictures",
    "musica": "Music",
    "videos": "Videos",
    "carpeta personal": "",
    "jarvis": "Desktop/Jarvis",
}

_DOMAIN_RE = re.compile(r"^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$")


def _start_menu_dirs() -> Iterable[Path]:
    for env in ("APPDATA", "PROGRAMDATA"):
        base = os.environ.get(env)
        if base:
            yield Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def find_start_menu_shortcut(
    name: str, dirs: Optional[Iterable[Path]] = None
) -> Optional[Path]:
    """Find an installed app's Start-menu shortcut whose name matches *name*."""
    wanted = _norm(name)
    if not wanted:
        return None
    best: Optional[Tuple[int, Path]] = None
    for root in dirs if dirs is not None else _start_menu_dirs():
        if not root.is_dir():
            continue
        for lnk in root.rglob("*.lnk"):
            stem = _norm(lnk.stem)
            if "uninstall" in stem or "desinstalar" in stem:
                continue
            if stem == wanted:
                return lnk
            if wanted in stem.split() or stem.startswith(wanted):
                score = len(stem)  # prefer the shortest (most specific) match
                if best is None or score < best[0]:
                    best = (score, lnk)
    return best[1] if best else None


def resolve_target(target: str) -> Tuple[str, str]:
    """Map a spoken request to ``(kind, value)``.

    ``kind`` is one of ``url``, ``app``, ``folder``, ``shortcut`` or
    ``unknown``.
    """
    key = _norm(target)
    for prefix in ("abre ", "abrir ", "pon ", "lanza ", "inicia "):
        if key.startswith(prefix):
            key = key[len(prefix) :]
    key = re.sub(r"^(?:la |el |mi |mis )", "", key)
    key = re.sub(
        r"^(?:carpeta de|carpeta|pagina de|pagina|web de"
        r"|aplicacion de|aplicacion|app de|app)\s+",
        "",
        key,
    )

    if key in WEBSITES:
        return "url", WEBSITES[key]
    if key in USER_FOLDERS:
        return "folder", str(Path.home() / USER_FOLDERS[key])
    if key in WINDOWS_APPS:
        return "app", WINDOWS_APPS[key]
    if _DOMAIN_RE.match(key) and " " not in key:
        url = key if key.startswith("http") else f"https://{key}"
        return "url", url
    shortcut = find_start_menu_shortcut(key)
    if shortcut is not None:
        return "shortcut", str(shortcut)
    return "unknown", key


def _launch(kind: str, value: str) -> None:
    if kind == "url":
        webbrowser.open(value)
        return
    if sys.platform == "win32":
        os.startfile(value)  # type: ignore[attr-defined]  # ShellExecute
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, value])


@ToolRegistry.register("open_app")
class OpenAppTool(BaseTool):
    """Open an installed app, a website or a user folder by its spoken name."""

    tool_id = "open_app"

    def __init__(self, launcher: Optional[Callable[[str, str], None]] = None) -> None:
        self._launcher = launcher or _launch

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="open_app",
            description=(
                "Open something on the user's Windows PC: an installed app "
                "(e.g. 'calculadora', 'excel', 'spotify', 'chrome'), a website "
                "(e.g. 'youtube', 'gmail', 'sunat.gob.pe') or a folder "
                "('descargas', 'documentos', 'escritorio'). Cannot run "
                "commands or delete anything."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Name of the app, website or folder, "
                        "as the user said it (Spanish is fine).",
                    }
                },
                "required": ["target"],
            },
            category="desktop",
            latency_estimate=1.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        target = str(params.get("target", "")).strip()
        if not target:
            return ToolResult(
                tool_name="open_app", content="Falta indicar qué abrir.", success=False
            )
        kind, value = resolve_target(target)
        if kind == "unknown":
            return ToolResult(
                tool_name="open_app",
                content=(
                    f"No encontré '{target}' entre las apps instaladas, webs o "
                    "carpetas conocidas. Pide al usuario el nombre exacto o la web."
                ),
                success=False,
            )
        if kind == "folder" and not Path(value).exists():
            return ToolResult(
                tool_name="open_app",
                content=f"La carpeta {value} no existe en este equipo.",
                success=False,
            )
        try:
            self._launcher(kind, value)
        except Exception as exc:
            return ToolResult(
                tool_name="open_app",
                content=f"No se pudo abrir '{target}': {exc}",
                success=False,
            )
        label = {
            "url": "la web",
            "app": "la aplicación",
            "shortcut": "la aplicación",
            "folder": "la carpeta",
        }[kind]
        return ToolResult(
            tool_name="open_app",
            content=f"Listo: abrí {label} '{target}' ({value}).",
            success=True,
            metadata={"kind": kind, "value": value},
        )


def _fmt_gb(num_bytes: float) -> str:
    return f"{num_bytes / 1024**3:.1f} GB"


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days} días y {hours} horas"
    if hours:
        return f"{hours} horas y {minutes} minutos"
    return f"{minutes} minutos"


def describe_system(psutil_mod: Any = None, now: Optional[float] = None) -> str:
    """Return a Spanish summary of battery, CPU, RAM, disk and uptime."""
    if psutil_mod is None:
        import psutil as psutil_mod  # type: ignore[no-redef]

    parts = []
    battery = None
    try:
        battery = psutil_mod.sensors_battery()
    except Exception:
        battery = None
    if battery is not None:
        estado = "cargando" if battery.power_plugged else "con batería"
        line = f"Batería al {round(battery.percent)} % ({estado})"
        secs = getattr(battery, "secsleft", None)
        if (
            not battery.power_plugged
            and isinstance(secs, (int, float))
            and 0 < secs < 10**6
        ):
            line += f", quedan unos {_fmt_duration(secs)}"
        parts.append(line + ".")

    cpu = psutil_mod.cpu_percent(interval=0.5)
    parts.append(f"Procesador al {round(cpu)} %.")

    mem = psutil_mod.virtual_memory()
    parts.append(
        f"Memoria RAM: {_fmt_gb(mem.used)} usados de {_fmt_gb(mem.total)} "
        f"({round(mem.percent)} %)."
    )

    disk_root = os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
    try:
        disk = psutil_mod.disk_usage(disk_root)
        parts.append(
            f"Disco {disk_root.rstrip(chr(92))}: {_fmt_gb(disk.free)} libres de "
            f"{_fmt_gb(disk.total)}."
        )
    except Exception:
        pass

    try:
        uptime = (now or time.time()) - psutil_mod.boot_time()
        parts.append(f"Encendida desde hace {_fmt_duration(uptime)}.")
    except Exception:
        pass
    return " ".join(parts)


@ToolRegistry.register("system_status")
class SystemStatusTool(BaseTool):
    """Battery, CPU, RAM, disk and uptime of the user's PC."""

    tool_id = "system_status"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="system_status",
            description=(
                "Report the state of the user's PC: battery level and charging, "
                "CPU and RAM usage, free disk space and uptime."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="desktop",
            latency_estimate=0.6,
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            return ToolResult(
                tool_name="system_status", content=describe_system(), success=True
            )
        except Exception as exc:
            return ToolResult(
                tool_name="system_status",
                content=f"No pude leer el estado del sistema: {exc}",
                success=False,
            )


# Windows virtual-key codes for media keys.
_VK = {
    "subir_volumen": 0xAF,
    "bajar_volumen": 0xAE,
    "silenciar": 0xAD,
    "play_pausa": 0xB3,
    "siguiente": 0xB0,
    "anterior": 0xB1,
}
_KEYEVENTF_KEYUP = 0x0002


def _press_media_key(vk: int, times: int = 1) -> None:
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


@ToolRegistry.register("media_control")
class MediaControlTool(BaseTool):
    """Volume and media playback keys (Windows)."""

    tool_id = "media_control"

    def __init__(self, presser: Optional[Callable[[int, int], None]] = None) -> None:
        self._presser = presser

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="media_control",
            description=(
                "Control volume and media playback on the user's Windows PC: "
                "raise/lower/mute volume, play or pause, next or previous track."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(_VK),
                        "description": "What to do.",
                    },
                    "steps": {
                        "type": "integer",
                        "description": "For volume up/down: how many steps of 2 % "
                        "(default 5, i.e. about 10 %).",
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["action"],
            },
            category="desktop",
        )

    def execute(self, **params: Any) -> ToolResult:
        action = str(params.get("action", "")).strip()
        if action not in _VK:
            return ToolResult(
                tool_name="media_control",
                content=f"Acción desconocida: {action!r}. Usa una de {list(_VK)}.",
                success=False,
            )
        presser = self._presser
        if presser is None:
            if sys.platform != "win32":
                return ToolResult(
                    tool_name="media_control",
                    content="El control multimedia solo está disponible en Windows.",
                    success=False,
                )
            presser = _press_media_key
        steps = 1
        if action in ("subir_volumen", "bajar_volumen"):
            try:
                steps = max(1, min(50, int(params.get("steps", 5))))
            except (TypeError, ValueError):
                steps = 5
        presser(_VK[action], steps)
        return ToolResult(
            tool_name="media_control",
            content=f"Hecho: {action.replace('_', ' ')}"
            + (f" ({steps} pasos)" if steps > 1 else "")
            + ".",
            success=True,
        )


__all__ = [
    "MediaControlTool",
    "OpenAppTool",
    "SystemStatusTool",
    "describe_system",
    "find_start_menu_shortcut",
    "resolve_target",
]
