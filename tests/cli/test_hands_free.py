"""Tests for the hands-free (wake word) voice mode."""

from __future__ import annotations

import io
import struct
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from openjarvis.cli._hands_free import (
    HandsFreeListener,
    extract_command,
    is_exit_command,
    wav_has_speech,
)
from openjarvis.cli._voice_chat import VOICE_EXIT


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Oye Jarvis, ¿qué hora es?", "¿qué hora es?"),
        ("Jarvis dime el clima", "dime el clima"),
        ("Yarvis, abre el navegador", "abre el navegador"),
        ("¿Qué hora es, Jarvis?", "¿Qué hora es"),
        ("Jarvis.", ""),
        ("hola Harvis", ""),
        ("estaba hablando con mi mamá", None),
        # Spanish Whisper mis-hearing "Jarvis" (seen on a real laptop).
        ("Ya lo viste, ¿qué hora es?", "¿qué hora es?"),
        ("¡Ya lo viste! ¡Ya lo viste! ¡Qué hora es!", "Qué hora es"),
        ("Ya lo vis, abre YouTube", "abre YouTube"),
        ("ayer ya lo viste el partido", None),
        ("Jarvis, Jarvis, abre YouTube", "abre YouTube"),
        ("Jarvis — abre YouTube", "abre YouTube"),
        ("", None),
    ],
)
def test_extract_command(text, expected):
    assert extract_command(text) == expected


def test_custom_wake_word():
    assert extract_command("Viernes, qué hora es", "viernes") == "qué hora es"
    assert extract_command("Jarvis, qué hora es", "viernes") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("apágate", True),
        ("Desconéctate por favor", True),
        ("adiós", True),
        ("cómo se dice adiós en inglés", False),
        ("qué hora es", False),
    ],
)
def test_is_exit_command(text, expected):
    assert is_exit_command(text) is expected


def _wav(amplitude: int, samples: int = 4096) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(
            struct.pack(f"{samples}h", *([amplitude, -amplitude] * (samples // 2)))
        )
    return buf.getvalue()


def test_wav_has_speech():
    assert wav_has_speech(_wav(3000))
    assert not wav_has_speech(_wav(50))
    assert not wav_has_speech(b"not a wav")


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _listener(clock=None, speak=None):
    return HandsFreeListener(
        MagicMock(),
        MagicMock(),
        speak_fn=speak,
        clock=clock or _Clock(),
        follow_up_seconds=8.0,
    )


def test_ignores_background_talk():
    assert _listener().handle_transcript("y entonces fuimos al mercado") is None


def test_wake_word_with_request():
    assert _listener().handle_transcript("Jarvis, qué hora es") == "qué hora es"


def test_wake_word_alone_acknowledges_and_opens_window():
    clock = _Clock()
    spoken = []
    listener = _listener(clock, spoken.append)
    assert listener.handle_transcript("Jarvis") is None
    assert spoken == ["¿Sí, señor?"]
    # Follow-up without the wake word is accepted inside the window...
    clock.now += 5
    assert listener.handle_transcript("pon música") == "pon música"


def test_follow_up_window_expires():
    clock = _Clock()
    listener = _listener(clock)
    listener.mark_awake()
    clock.now += 3
    assert listener.handle_transcript("y mañana?") == "y mañana?"
    listener.mark_awake()
    clock.now += 9
    assert listener.handle_transcript("y pasado?") is None


def test_exit_by_voice():
    assert _listener().handle_transcript("Jarvis, apágate") is VOICE_EXIT


def test_listen_loop_skips_silence_and_returns_request(monkeypatch):
    session = MagicMock()
    backend = MagicMock()
    backend.transcribe.side_effect = [
        SimpleNamespace(text="charla de fondo"),
        SimpleNamespace(text="Jarvis, qué hora es"),
    ]
    session.get_stt_backend.return_value = backend
    session.get_stt_language.return_value = "es"
    listener = HandsFreeListener(MagicMock(), session)
    recordings = iter([_wav(10), _wav(3000), _wav(3000)])
    monkeypatch.setattr(listener, "_record", lambda: next(recordings))

    assert listener.listen() == "qué hora es"
    # The silent recording was never transcribed.
    assert backend.transcribe.call_count == 2


def test_listen_without_stt_backend_exits():
    session = MagicMock()
    session.get_stt_backend.return_value = None
    assert HandsFreeListener(MagicMock(), session).listen() is VOICE_EXIT


def test_transcribe_biases_faster_whisper_toward_wake_word():
    session = MagicMock()
    session.get_stt_language.return_value = "es"
    backend = MagicMock(backend_id="faster-whisper")
    HandsFreeListener(MagicMock(), session)._transcribe(backend, b"wav")
    kwargs = backend.transcribe.call_args.kwargs
    assert kwargs["hotwords"] == "Jarvis"
    assert "Jarvis" in kwargs["initial_prompt"]
    assert kwargs["language"] == "es"


def test_transcribe_other_backends_get_plain_call():
    session = MagicMock()
    session.get_stt_language.return_value = "es"
    backend = MagicMock(backend_id="deepgram")
    HandsFreeListener(MagicMock(), session)._transcribe(backend, b"wav")
    assert backend.transcribe.call_args.kwargs == {"format": "wav", "language": "es"}
