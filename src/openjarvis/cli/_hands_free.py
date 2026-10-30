"""Hands-free voice mode: always listening, activated by a wake word.

The microphone is open continuously. Every utterance is transcribed locally
with the configured STT backend (faster-whisper by default); only utterances
that contain the wake word ("Jarvis") reach the agent. After Jarvis answers,
a short follow-up window lets the user keep talking without repeating the
wake word, like a natural conversation.

Detecting the wake word from the transcript keeps this dependency-free (no
extra wake-word model to download or train) at the cost of running Whisper on
every utterance, which is fine on a modern CPU.
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
import wave
from typing import Any, Callable, Optional

from openjarvis.cli._voice_chat import VOICE_EXIT, VoiceSession, _terminal_safe_text

DEFAULT_WAKE_WORD = "jarvis"
FOLLOW_UP_SECONDS = 8.0
_SPEECH_RMS_THRESHOLD = 500

# Whisper often hears "Jarvis" as "Yarvis", "Jarvi", "Harvis", "Llarvis"...
_JARVIS_VARIANTS = r"(?:j|y|ll|h|ch|sh)?ar[bv]i[sz]?|jarbis|jervis|yervis"

# Spoken commands that end the hands-free session.
_EXIT_PHRASES = (
    "apagate",
    "desconectate",
    "termina la sesion",
    "cierra la sesion",
    "hasta luego",
    "adios",
)


def _normalize(text: str) -> str:
    """Lowercase and strip accents/punctuation for robust matching."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    no_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^\w\s]", " ", no_accents)


def _wake_pattern(wake_word: str) -> re.Pattern[str]:
    word = _normalize(wake_word).strip()
    if word == DEFAULT_WAKE_WORD:
        body = _JARVIS_VARIANTS
    else:
        body = re.escape(word)
    return re.compile(rf"\b(?:{body})\b")


def extract_command(text: str, wake_word: str = DEFAULT_WAKE_WORD) -> Optional[str]:
    """Return the request that follows/surrounds the wake word, or None.

    ``"Oye Jarvis, ¿qué hora es?"`` → ``"¿qué hora es?"``.
    ``"Jarvis"`` alone → ``""`` (woken up, no request yet).
    Text without the wake word → ``None``.
    """
    normalized = _normalize(text)
    match = _wake_pattern(wake_word).search(normalized)
    if match is None:
        return None
    # Map the normalized match back onto the original text by word index.
    words_before = len(normalized[: match.start()].split())
    original_words = text.split()
    remaining = original_words[words_before + 1 :]
    # Leading filler before the wake word ("oye", "hola") is dropped; anything
    # meaningful after it is the request.
    command = " ".join(remaining).strip(" ,.;:!¡")
    if not command and words_before > 0:
        before = " ".join(original_words[:words_before]).strip(" ,.;:!¡")
        if _normalize(before).strip() not in ("oye", "hola", "hey", "ey", "ok"):
            command = before
    return command


def is_exit_command(text: str) -> bool:
    """True for a short goodbye like "apágate" (not "¿cómo se dice adiós?")."""
    words = _normalize(text).split()
    if not words or len(words) > 4:
        return False
    normalized = " ".join(words)
    return any(normalized.startswith(phrase) for phrase in _EXIT_PHRASES)


def wav_has_speech(wav_bytes: bytes, threshold: int = _SPEECH_RMS_THRESHOLD) -> bool:
    """True if any 1024-sample chunk of a 16-bit WAV is louder than *threshold*."""
    from openjarvis.speech.voice_io import _rms

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
    except Exception:
        return False
    step = 2048  # 1024 samples * 2 bytes
    return any(
        _rms(frames[i : i + step]) > threshold for i in range(0, len(frames), step)
    )


class HandsFreeListener:
    """Continuous listen → transcribe → wake-word gate loop."""

    def __init__(
        self,
        console: Any,
        session: VoiceSession,
        *,
        wake_word: str = DEFAULT_WAKE_WORD,
        follow_up_seconds: float = FOLLOW_UP_SECONDS,
        speak_fn: Optional[Callable[[str], None]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._console = console
        self._session = session
        self._wake_word = wake_word
        self._follow_up_seconds = follow_up_seconds
        self._speak_fn = speak_fn
        self._clock = clock
        self._awake_until = 0.0
        self._announced = False

    def mark_awake(self) -> None:
        """Open the follow-up window (call right after Jarvis finishes talking)."""
        self._awake_until = self._clock() + self._follow_up_seconds

    def _is_awake(self) -> bool:
        return self._clock() < self._awake_until

    def _record(self) -> bytes:
        from openjarvis.speech.voice_io import record_until_silence

        return record_until_silence(startup_silence_seconds=4.0)

    def handle_transcript(self, text: str) -> Optional[str] | object:
        """Decide what to do with one transcribed utterance."""
        text = text.strip()
        if not text:
            return None

        awake = self._is_awake()
        command = extract_command(text, self._wake_word)

        if command is None and not awake:
            return None  # background talk: ignore silently

        request = text if command is None else command
        if is_exit_command(request):
            return VOICE_EXIT

        self._console.print(f"[bold]You (voice):[/bold] {_terminal_safe_text(text)}")
        if not request:
            # Just "Jarvis": acknowledge and wait for the actual request.
            if self._speak_fn is not None:
                self._speak_fn("¿Sí, señor?")
            self.mark_awake()
            return None
        return request

    def listen(self) -> Optional[str] | object:
        """Block until a request addressed to Jarvis is heard."""
        if not self._announced:
            self._console.print(
                f"[magenta]Manos libres activo[/magenta] — di "
                f'"[bold]{self._wake_word.capitalize()}[/bold]" y tu pedido. '
                'Para salir di "Jarvis, apágate" o pulsa Ctrl+C.'
            )
            self._announced = True

        backend = self._session.get_stt_backend()
        if backend is None:
            self._console.print(
                "[red]No hay reconocimiento de voz disponible. Instala: "
                "uv sync --extra speech[/red]"
            )
            return VOICE_EXIT

        while True:
            if self._is_awake():
                self._console.print("[dim cyan]Te escucho…[/dim cyan]")
            try:
                audio = self._record()
            except KeyboardInterrupt:
                return VOICE_EXIT
            except Exception as exc:
                self._console.print(
                    f"[red]Error de micrófono: {_terminal_safe_text(exc)}[/red]"
                )
                return VOICE_EXIT

            if not wav_has_speech(audio):
                continue

            try:
                result = backend.transcribe(
                    audio, format="wav", language=self._session.get_stt_language()
                )
            except KeyboardInterrupt:
                return VOICE_EXIT
            except Exception as exc:
                self._console.print(
                    f"[red]Error de transcripción: {_terminal_safe_text(exc)}[/red]"
                )
                continue

            outcome = self.handle_transcript(result.text)
            if outcome is None:
                continue
            return outcome


__all__ = [
    "DEFAULT_WAKE_WORD",
    "HandsFreeListener",
    "extract_command",
    "is_exit_command",
    "wav_has_speech",
]
