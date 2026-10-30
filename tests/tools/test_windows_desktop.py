"""Tests for the Windows desktop tools (open_app, system_status, media_control)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from openjarvis.tools import windows_desktop as wd


@pytest.mark.parametrize(
    ("spoken", "kind", "value"),
    [
        ("YouTube", "url", "https://www.youtube.com"),
        ("página de gmail", "url", "https://mail.google.com"),
        ("sunat.gob.pe", "url", "https://sunat.gob.pe"),
        ("https://example.com/x", "url", "https://example.com/x"),
        ("la calculadora", "app", "calc"),
        ("abre Excel", "app", "excel"),
        ("configuración", "app", "ms-settings:"),
        ("bloc de notas", "app", "notepad"),
    ],
)
def test_resolve_target_known(spoken, kind, value):
    assert wd.resolve_target(spoken) == (kind, value)


def test_resolve_target_folder():
    kind, value = wd.resolve_target("abre la carpeta de descargas")
    assert kind == "folder"
    assert value == str(Path.home() / "Downloads")


def test_resolve_target_start_menu(tmp_path, monkeypatch):
    programs = tmp_path / "Programs" / "Zoom"
    programs.mkdir(parents=True)
    (programs / "Zoom Workplace.lnk").write_bytes(b"")
    (programs / "Uninstall Zoom.lnk").write_bytes(b"")
    monkeypatch.setattr(wd, "_start_menu_dirs", lambda: [tmp_path / "Programs"])
    kind, value = wd.resolve_target("zoom")
    assert kind == "shortcut"
    assert value.endswith("Zoom Workplace.lnk")


def test_resolve_target_unknown(monkeypatch):
    monkeypatch.setattr(wd, "_start_menu_dirs", lambda: [])
    assert wd.resolve_target("programa inexistente xyz")[0] == "unknown"


def test_open_app_calls_launcher():
    calls = []
    tool = wd.OpenAppTool(launcher=lambda kind, value: calls.append((kind, value)))
    result = tool.execute(target="youtube")
    assert result.success
    assert calls == [("url", "https://www.youtube.com")]


def test_open_app_unknown_does_not_launch(monkeypatch):
    monkeypatch.setattr(wd, "_start_menu_dirs", lambda: [])
    calls = []
    tool = wd.OpenAppTool(launcher=lambda kind, value: calls.append(value))
    result = tool.execute(target="cosa rarísima")
    assert not result.success
    assert calls == []


def test_open_app_reports_launch_error():
    def boom(kind, value):
        raise OSError("no app")

    result = wd.OpenAppTool(launcher=boom).execute(target="excel")
    assert not result.success
    assert "no app" in result.content


def test_open_app_requires_target():
    assert not wd.OpenAppTool(launcher=lambda k, v: None).execute(target="").success


def test_describe_system_spanish():
    fake = SimpleNamespace(
        sensors_battery=lambda: SimpleNamespace(
            percent=81.6, power_plugged=False, secsleft=7200
        ),
        cpu_percent=lambda interval=None: 12.0,
        virtual_memory=lambda: SimpleNamespace(
            used=8 * 1024**3, total=24 * 1024**3, percent=33.3
        ),
        disk_usage=lambda path: SimpleNamespace(
            free=100 * 1024**3, total=500 * 1024**3
        ),
        boot_time=lambda: 1000.0,
    )
    text = wd.describe_system(fake, now=1000.0 + 3 * 3600 + 15 * 60)
    assert "Batería al 82 % (con batería), quedan unos 2 horas y 0 minutos" in text
    assert "Procesador al 12 %" in text
    assert "8.0 GB usados de 24.0 GB" in text
    assert "100.0 GB libres" in text
    assert "3 horas y 15 minutos" in text


def test_describe_system_without_battery():
    fake = SimpleNamespace(
        sensors_battery=lambda: None,
        cpu_percent=lambda interval=None: 5.0,
        virtual_memory=lambda: SimpleNamespace(used=1, total=2, percent=50),
        disk_usage=lambda path: SimpleNamespace(free=1, total=2),
        boot_time=lambda: 0.0,
    )
    assert "Batería" not in wd.describe_system(fake, now=60.0)


def test_media_control_volume_steps():
    pressed = []
    tool = wd.MediaControlTool(presser=lambda vk, n: pressed.append((vk, n)))
    assert tool.execute(action="subir_volumen", steps=3).success
    assert tool.execute(action="play_pausa").success
    assert pressed == [(0xAF, 3), (0xB3, 1)]


def test_media_control_rejects_unknown_action():
    tool = wd.MediaControlTool(presser=lambda vk, n: None)
    assert not tool.execute(action="formatear_disco").success
