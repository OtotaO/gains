"""mediapipe must stay below 1.0 until a 1.x release is re-tested on real hardware.

Regression: mediapipe 1.0.1 imported fine and exposed every symbol
`services/vision/nod.py` uses, then hard-crashed when the graph opened its Metal
service (`DrishtiMetalHelper`, Apple silicon). Later 1.x releases are untested on
hardware. CI installs only `.[dev]`, never the `vision` extra, so no other test
can see this. PRs #51 and #64 were closed for it, but closing a PR does not stop
a fresh `pip install -e ".[vision]"` from resolving the newest 1.x. The cap in
pyproject.toml does.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[1]


def _vision_mediapipe() -> Requirement:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"]
    for spec in project["optional-dependencies"]["vision"]:
        requirement = Requirement(spec)
        if requirement.name == "mediapipe":
            return requirement
    raise AssertionError("the vision extra no longer lists mediapipe")


def test_vision_extra_caps_mediapipe_below_1() -> None:
    specifier = _vision_mediapipe().specifier
    assert specifier.contains("0.10.35")
    # 1.0.1 is the release that crashed; the others are untested 1.x releases.
    for excluded in ("1.0.0", "1.0.1", "1.2.3"):
        assert not specifier.contains(excluded), f"vision extra admits mediapipe {excluded}"


def test_dependabot_does_not_propose_mediapipe_1() -> None:
    config = yaml.safe_load((REPO_ROOT / ".github" / "dependabot.yml").read_text())
    pip_entries = [e for e in config["updates"] if e["package-ecosystem"] == "pip"]
    assert pip_entries, "no pip entry in dependabot.yml"
    for entry in pip_entries:
        ignored = [i for i in entry.get("ignore", []) if i.get("dependency-name") == "mediapipe"]
        assert ignored, f"pip entry {entry['directory']} does not ignore mediapipe 1.x"
        assert ">=1.0.0" in ignored[0].get("versions", [])
