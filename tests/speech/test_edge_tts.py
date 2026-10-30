"""Tests for the Edge TTS backend and the current_datetime tool."""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech import edge_tts_backend as edge


def test_speed_to_rate():
    assert edge._speed_to_rate(1.0) == "+0%"
    assert edge._speed_to_rate(1.15) == "+15%"
    assert edge._speed_to_rate(0.8) == "-20%"
    assert edge._speed_to_rate(5.0) == "+100%"  # clamped
    assert edge._speed_to_rate(0.1) == "-50%"  # clamped


def test_edge_registered():
    TTSRegistry.register_value("edge_tts", edge.EdgeTTSBackend)
    assert TTSRegistry.contains("edge_tts")


def test_synthesize_mp3_passthrough():
    async def fake(text, voice, rate):
        assert voice == "es-PE-CamilaNeural"
        assert rate == "+10%"
        return b"fake-mp3"

    with patch.object(edge, "_synthesize_async", fake):
        result = edge.EdgeTTSBackend().synthesize(
            "hola", voice_id="es-PE-CamilaNeural", speed=1.1
        )
    assert result.audio == b"fake-mp3"
    assert result.format == "mp3"
    assert result.voice_id == "es-PE-CamilaNeural"


def test_synthesize_default_voice():
    seen = {}

    async def fake(text, voice, rate):
        seen["voice"] = voice
        return b"x"

    with patch.object(edge, "_synthesize_async", fake):
        edge.EdgeTTSBackend().synthesize("hola", voice_id="")
    assert seen["voice"] == edge.DEFAULT_VOICE


def test_synthesize_wav_conversion():
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    if "MP3" not in sf.available_formats():
        pytest.skip("libsndfile built without MP3 support")

    t = np.linspace(0, 0.3, 7200)
    buf = io.BytesIO()
    sf.write(
        buf, (np.sin(2 * np.pi * 440 * t) * 0.3).astype("float32"), 24000, format="MP3"
    )

    async def fake(text, voice, rate):
        return buf.getvalue()

    with patch.object(edge, "_synthesize_async", fake):
        result = edge.EdgeTTSBackend().synthesize("hola", output_format="wav")
    assert result.format == "wav"
    assert result.audio[:4] == b"RIFF"


def test_synthesize_empty_audio_raises():
    async def fake(text, voice, rate):
        return b""

    with patch.object(edge, "_synthesize_async", fake):
        with pytest.raises(RuntimeError):
            edge.EdgeTTSBackend().synthesize("hola")


def test_run_coro_inside_running_loop():
    async def inner():
        return 42

    async def outer():
        return edge._run_coro(inner())

    assert asyncio.run(outer()) == 42


def test_describe_now_spanish():
    from openjarvis.tools.current_datetime import describe_now

    lima = timezone(timedelta(hours=-5))
    text = describe_now(datetime(2026, 10, 29, 20, 33, tzinfo=lima))
    assert "jueves 29 de octubre de 2026" in text
    assert "20:33" in text
    assert "noche" in text
    assert "UTC-05:00" in text


def test_current_datetime_tool_registered():
    from openjarvis.core.registry import ToolRegistry
    from openjarvis.tools.current_datetime import CurrentDateTimeTool

    # The test conftest clears registries between tests, so re-register.
    ToolRegistry.register_value("current_datetime", CurrentDateTimeTool)
    assert ToolRegistry.contains("current_datetime")
    tool = ToolRegistry.get("current_datetime")()
    result = tool.execute()
    assert result.success
    assert "Hoy es" in result.content
