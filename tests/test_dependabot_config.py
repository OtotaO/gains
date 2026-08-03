"""Every Dependabot entry must point at a manifest that actually exists.

Regression: `.github/dependabot.yml` carried an `npm` ecosystem for
`/tauri-app`, which is a Trunk + Leptos (Rust/wasm) frontend with no
package.json. Dependabot therefore failed every week with "Error during file
fetching; aborting: /tauri-app/package.json not found" — a standing red run
that masks real failures. Nothing else in CI would have caught it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / ".github" / "dependabot.yml"

# The file Dependabot fetches to discover dependencies for each ecosystem.
# https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
MANIFESTS: dict[str, tuple[str, ...]] = {
    "cargo": ("Cargo.toml",),
    "npm": ("package.json",),
    "pip": ("pyproject.toml", "setup.py", "requirements.txt", "setup.cfg"),
    "github-actions": (".github/workflows",),
}


def _updates() -> list[dict]:
    config = yaml.safe_load(CONFIG.read_text())
    return config["updates"]


def test_config_parses() -> None:
    assert _updates(), "dependabot.yml declares no updates"


@pytest.mark.parametrize("entry", _updates(), ids=lambda e: f"{e['package-ecosystem']}:{e['directory']}")
def test_every_entry_has_a_manifest(entry: dict) -> None:
    ecosystem = entry["package-ecosystem"]
    directory = entry["directory"].lstrip("/")
    candidates = MANIFESTS.get(ecosystem)
    assert candidates is not None, f"unknown ecosystem {ecosystem!r} — extend MANIFESTS"

    target = REPO_ROOT / directory
    found = [name for name in candidates if (target / name).exists()]
    assert found, (
        f"dependabot.yml declares {ecosystem} updates for /{directory}, but none of "
        f"{list(candidates)} exists there. Dependabot will fail on every run."
    )


def test_no_npm_entry_for_the_rust_frontend() -> None:
    """Pin the specific defect: tauri-app is Rust/wasm, it has no package.json."""
    assert not (REPO_ROOT / "tauri-app" / "package.json").exists()
    offenders = [
        e
        for e in _updates()
        if e["package-ecosystem"] == "npm" and e["directory"].lstrip("/") == "tauri-app"
    ]
    assert offenders == []
