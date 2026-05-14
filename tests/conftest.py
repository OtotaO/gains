"""Shared pytest fixtures."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

# Make the repo root importable so ``services.*`` and ``plugins.*`` resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def free_port() -> int:
    return _free_port()
