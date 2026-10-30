"""Microsoft Edge TTS backend — free neural voices, no API key.

Uses the ``edge-tts`` package, which talks to the same online service the
Edge browser uses for "Read aloud". It needs internet access but no account
or key, and it has natural voices in many Spanish variants, including
Peruvian Spanish (``es-PE-AlexNeural`` and ``es-PE-CamilaNeural``).

Install with: ``uv sync --extra voice-edge``
"""

from __future__ import annotations

import asyncio
import io
import threading
from typing import Any, List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

DEFAULT_VOICE = "es-PE-AlexNeural"
_SAMPLE_RATE = 24000  # edge-tts streams 24 kHz mono MP3


def _speed_to_rate(speed: float) -> str:
    """Convert a speed multiplier (1.0 = normal) to edge-tts ``rate`` syntax."""
    pct = round((float(speed) - 1.0) * 100)
    pct = max(-50, min(100, pct))
    return f"{pct:+d}%"


async def _synthesize_async(text: str, voice: str, rate: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def _run_coro(coro: Any) -> Any:
    """Run *coro* to completion even when called from inside a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Already inside an event loop (e.g. the API server): run in a thread.
    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # re-raised in the caller's thread
            box["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def _mp3_to_wav(mp3: bytes) -> bytes | None:
    """Decode MP3 to 16-bit WAV with soundfile; return None if unsupported."""
    try:
        import soundfile as sf

        data, sample_rate = sf.read(io.BytesIO(mp3), dtype="int16")
        out = io.BytesIO()
        sf.write(out, data, sample_rate, format="WAV", subtype="PCM_16")
        return out.getvalue()
    except Exception:
        return None


@TTSRegistry.register("edge_tts")
class EdgeTTSBackend(TTSBackend):
    """Free online neural TTS via Microsoft Edge voices."""

    backend_id = "edge_tts"

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = DEFAULT_VOICE,
        speed: float = 1.0,
        output_format: str = "mp3",
    ) -> TTSResult:
        voice = voice_id or DEFAULT_VOICE
        mp3 = _run_coro(_synthesize_async(text, voice, _speed_to_rate(speed)))
        if not mp3:
            raise RuntimeError(f"edge-tts returned no audio for voice {voice!r}")

        audio, fmt = mp3, "mp3"
        if output_format == "wav":
            wav = _mp3_to_wav(mp3)
            if wav is not None:
                audio, fmt = wav, "wav"

        return TTSResult(
            audio=audio,
            format=fmt,
            voice_id=voice,
            sample_rate=_SAMPLE_RATE,
            metadata={"backend": self.backend_id},
        )

    def available_voices(self) -> List[str]:
        try:
            import edge_tts

            voices = _run_coro(edge_tts.list_voices())
            return sorted(v["ShortName"] for v in voices)
        except Exception:
            return [DEFAULT_VOICE, "es-PE-CamilaNeural"]

    def health(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True


__all__ = ["DEFAULT_VOICE", "EdgeTTSBackend"]
