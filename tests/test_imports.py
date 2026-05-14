"""Smoke-test that each module's source parses and core symbols import.

We intentionally do not import modules whose top-level side effects open
audio / camera / network handles (asr, vision, tts) — those are validated
by parsing their source. The bus, notes exporter, plugin runner, and the
two sample plugins are safe to import.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

SOURCE_ONLY = [
    "services/asr/server.py",
    "services/vision/nod.py",
    "services/tts/voice.py",
]

IMPORTABLE = [
    "services.bus.hub",
    "services.notes.exporter",
    "services.plugins.runner",
    "plugins.grammar_guard.plugin",
    "plugins.sample_rewriter.plugin",
]


@pytest.mark.parametrize("relpath", SOURCE_ONLY)
def test_module_parses(relpath: str) -> None:
    src = (REPO / relpath).read_text()
    ast.parse(src, filename=relpath)


@pytest.mark.parametrize("modname", IMPORTABLE)
def test_module_imports(modname: str) -> None:
    __import__(modname)
