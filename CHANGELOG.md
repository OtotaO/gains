# Changelog

## Unreleased — Phase 1 modernization (branch `claude/assess-modernization-61ThF`)

### Breaking

* **Bus wiring changed.** Services that publish events must now connect
  their PUB to `tcp://localhost:5556` (the XSUB side of the bus). The
  previous design had every publisher connect to the same PUB endpoint
  the hub was bound on, which transmitted nothing — so this is a fix
  rather than a behavioural break. The Tauri SUB bridge still connects
  to `tcp://localhost:5555` (the XPUB side).
* **`tauri-app/` is now Tauri 2 + Leptos 0.8**, replacing the previous
  Tauri 2.0.0-beta.9 + vanilla TS shell.
* **Allowlist removed** from `tauri.conf.json` in favour of Tauri v2
  capability files.
* **Plug-in `text.committed` contract honoured.** The shell now actually
  publishes a `text.committed` event when a nod is detected — previously
  the `commit_text` command only printed to stdout, so the plug-in
  pipeline never fired.

### Repository

* Collapsed three parallel Tauri shells and two duplicate Python service
  trees into a single canonical layout (`tauri-app/`, `services/`,
  `plugins/`).

### Python services

* Fixed unsatisfiable `avg_logprob > 0.7` confidence gate in ASR (Whisper
  log-probs are negative — gate never opened).
* Moved heavy `model.transcribe` out of the `sounddevice` audio callback
  into a worker thread to prevent dropped audio.
* Added YAML-driven multilingual / model-size selection to ASR.
* Migrated vision from legacy `mp.solutions.face_mesh` to MediaPipe Tasks
  `FaceLandmarker`; pitch now from the facial transformation matrix.
* Piper TTS path now actually loads `piper-tts` (was a dead `ImportError`
  stub since landing).
* Note exporter no longer prompts interactively on startup.
* Plug-in runner now spawns subprocesses (was importing in-process,
  which blocked on the first plug-in's `while True`).
* Grammar Guard migrated from removed `openai.ChatCompletion.create` to
  the openai-python v1 client API; default model `gpt-4o-mini`.

### Tauri shell

* `tauri = "2"`, `leptos = "0.8"`, plus `tauri-plugin-{updater,shell,opener}` 2.x.
* Real CSP (was `null`); capability file includes `core:event:default`,
  `shell:default`, `updater:default`.
* ZMQ subscriber bridge ported from the deleted beta.9 shell; new
  publisher side wired so commands can emit bus events.
* UI replaces the greet demo with a live-caption view, nod-commit
  indicator, plug-in rewrite display, and an updater-check button.

### CI & tooling

* New `ci.yml` PR workflow: ruff + pytest + pip-audit, cargo
  fmt/clippy/check, wasm32 cargo check, cargo-deny.
* Release workflow rewritten around `tauri-apps/tauri-action@v0`; drops
  the bogus `brew install notarytool` step and switches to v2 signing
  env vars (`TAURI_SIGNING_PRIVATE_KEY*`).
* `pyproject.toml` (PEP 621) with optional dep groups (asr, asr-cuda,
  vision, tts, plugins, dev) and ruff/pytest/mypy config.
* `tests/` with proper pytest, replacing the three ad-hoc root-level
  `test_*.py` scripts.
* `Cargo.lock` now tracked (binary crate); `.gitignore`, `.editorconfig`,
  `rustfmt.toml`, `cargo-deny` config, Dependabot config added.

### Docs

* `docs/modernization-assessment.md` — multi-phase audit and roadmap.
* `README.md` rewritten with architecture diagram, event reference,
  quick-start, and modernization status.
* `docs/plugins.md` rewritten with the new bus wiring and a fully-runnable
  template.
