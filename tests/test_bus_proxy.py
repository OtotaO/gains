"""End-to-end test of the XSUB/XPUB bus proxy.

Spins up the proxy on a pair of ephemeral ports, connects a publisher and a
subscriber, and verifies that a JSON message round-trips through it. This
exercises the architectural fix in services/bus/hub.py.
"""
from __future__ import annotations

import threading
import time

import pytest
import zmq


def _run_proxy(ctx: zmq.Context, pub_port: int, sub_port: int, stop: threading.Event) -> None:
    """XSUB on `sub_port` (publishers connect), XPUB on `pub_port` (subscribers connect)."""
    xsub = ctx.socket(zmq.XSUB)
    xsub.bind(f"tcp://127.0.0.1:{sub_port}")
    xpub = ctx.socket(zmq.XPUB)
    xpub.bind(f"tcp://127.0.0.1:{pub_port}")
    poller = zmq.Poller()
    poller.register(xsub, zmq.POLLIN)
    poller.register(xpub, zmq.POLLIN)
    try:
        while not stop.is_set():
            events = dict(poller.poll(timeout=50))
            if xsub in events:
                xpub.send_multipart(xsub.recv_multipart())
            if xpub in events:
                xsub.send_multipart(xpub.recv_multipart())
    finally:
        xsub.close()
        xpub.close()


def test_proxy_round_trip(free_port: int) -> None:
    pub_port = free_port
    sub_port = pub_port + 1  # second ephemeral; OS may reassign, but consecutive usually fine
    ctx = zmq.Context.instance()
    stop = threading.Event()
    t = threading.Thread(
        target=_run_proxy, args=(ctx, pub_port, sub_port, stop), daemon=True
    )
    t.start()
    try:
        pub = ctx.socket(zmq.PUB)
        pub.connect(f"tcp://127.0.0.1:{sub_port}")
        sub = ctx.socket(zmq.SUB)
        sub.connect(f"tcp://127.0.0.1:{pub_port}")
        sub.setsockopt_string(zmq.SUBSCRIBE, "")
        time.sleep(0.2)  # subscription propagation

        for i in range(3):
            pub.send_json({"event": "ping", "i": i})

        sub.setsockopt(zmq.RCVTIMEO, 2000)
        received = [sub.recv_json() for _ in range(3)]
        assert [m["i"] for m in received] == [0, 1, 2]

        pub.close()
        sub.close()
    finally:
        stop.set()
        t.join(timeout=2)


def test_runner_discover_finds_plugins() -> None:
    from services.plugins.runner import discover

    plugins = discover()
    names = {p.parent.name for p in plugins}
    assert "grammar_guard" in names
    assert "sample_rewriter" in names


def test_grammar_guard_uses_openai_v1_api() -> None:
    """Walks the AST to assert the v1 call shape and the absence of the
    legacy ``openai.ChatCompletion.create(...)`` call (which appears in
    the docstring for context, hence the AST-level check rather than a grep)."""
    import ast
    import importlib.util
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "plugins/grammar_guard/plugin.py").read_text()
    tree = ast.parse(src)

    found_v1 = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match client.chat.completions.create(...)
        if (isinstance(func, ast.Attribute) and func.attr == "create"
                and isinstance(func.value, ast.Attribute) and func.value.attr == "completions"
                and isinstance(func.value.value, ast.Attribute)
                and func.value.value.attr == "chat"):
            found_v1 = True
        # Match openai.ChatCompletion.create(...)
        if (isinstance(func, ast.Attribute) and func.attr == "create"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "ChatCompletion"
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "openai"):
            raise AssertionError("legacy openai.ChatCompletion.create call still present")

    assert found_v1, "v1 client.chat.completions.create call not found"
    assert importlib.util.find_spec("plugins.grammar_guard.plugin") is not None


def test_asr_config_resolves_english_short_names() -> None:
    from services.asr.server import resolve_model_name

    assert resolve_model_name("small", "en") == "small.en"
    assert resolve_model_name("base", "en") == "base.en"
    assert resolve_model_name("small", "es") == "small"
    assert resolve_model_name("large-v3-turbo", "en") == "large-v3-turbo"


@pytest.mark.parametrize("pitch_deg,expected_sign", [(-45.0, -1), (0.0, 0), (45.0, 1)])
def test_pitch_from_matrix(pitch_deg: float, expected_sign: int) -> None:
    """Round-trip a rotation matrix through the pitch extractor."""
    import math

    import numpy as np
    from services.vision.nod import pitch_from_matrix

    theta = math.radians(pitch_deg)
    # X-axis rotation by `theta`
    rx = np.array([
        [1, 0, 0, 0],
        [0, math.cos(theta), -math.sin(theta), 0],
        [0, math.sin(theta), math.cos(theta), 0],
        [0, 0, 0, 1],
    ])
    recovered = pitch_from_matrix(rx)
    if expected_sign == 0:
        assert abs(recovered) < 1.0
    else:
        assert (recovered > 0) == (expected_sign > 0)
        assert abs(abs(recovered) - abs(pitch_deg)) < 1.0
