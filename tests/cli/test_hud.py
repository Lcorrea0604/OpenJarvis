"""Tests for the JARVIS HUD server and its wiring into hands-free mode."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from unittest.mock import MagicMock

import pytest

from openjarvis.cli._hud import HudServer, NullHud, start_hud


@pytest.fixture
def hud():
    server = HudServer(port=0)
    yield server
    server.stop()


def test_serves_page(hud):
    html = urllib.request.urlopen(hud.url, timeout=5).read().decode("utf-8")
    assert "<canvas" in html
    assert "/events" in html


def test_unknown_path_404(hud):
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(hud.url + "nope", timeout=5)
    assert err.value.code == 404


def test_streams_and_replays_events(hud):
    hud.set_state("thinking")  # sent before the client connects → replayed
    received: list[dict] = []

    def reader():
        with urllib.request.urlopen(hud.url + "events", timeout=5) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if line.startswith("data:"):
                    received.append(json.loads(line[5:]))
                    if len(received) >= 3:
                        return

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    time.sleep(0.4)
    hud.heard("qué hora es")
    hud.reply("Son las diez, señor.")
    thread.join(5)

    assert received[0] == {"type": "state", "state": "thinking"}
    assert {"type": "heard", "text": "qué hora es"} in received
    assert {"type": "reply", "text": "Son las diez, señor."} in received


def test_level_is_normalized_and_throttled(hud):
    sent = []
    hud._broadcast = lambda event, remember=True: sent.append(event)
    hud.set_level(3000)
    hud.set_level(3000)  # within the throttle window → dropped
    assert sent == [{"type": "level", "value": 0.5}]
    hud._last_level_at = 0
    hud.set_level(10**6)
    assert sent[-1]["value"] == 1.0


def test_start_hud_falls_back_when_port_busy():
    busy = HudServer(port=0)
    try:
        console = MagicMock()
        result = start_hud(console, port=busy.port, open_window=False)
        assert isinstance(result, NullHud)
        assert not isinstance(result, HudServer)
    finally:
        busy.stop()


def test_hands_free_reports_to_hud():
    from openjarvis.cli._hands_free import HandsFreeListener

    hud = MagicMock()
    listener = HandsFreeListener(MagicMock(), MagicMock(), hud=hud)
    listener._on_level(100)
    listener._on_level(4000)
    listener._on_level(4000)
    assert hud.set_state.call_args_list == [(("listening",),)]
    assert listener.handle_transcript("Jarvis, qué hora es") == "qué hora es"
    hud.heard.assert_called_once_with("Jarvis, qué hora es")
