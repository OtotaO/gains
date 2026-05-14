# GAINS Modernization Assessment

_Snapshot date: 2026-05-14. Branch: `claude/assess-modernization-61ThF`._

GAINS is a multi-modal note-taker: a Tauri desktop shell, a Python services
mesh (ASR / vision / TTS / notes / plugins), and a ZeroMQ pub/sub event bus
glueing them together. The repo currently contains **two parallel app trees**
(`tauri-app/` and `GAINS/`) at different maturity levels, with services
duplicated under each. This is the first thing to clean up.

The rest of this document walks the stack layer by layer, flags what is
outdated or risky, and proposes concrete modern replacements.

---

## 1. What's in the repo today

| Layer | Today | Where |
|---|---|---|
| Desktop shell A (old) | Tauri **2.0.0-beta.9** + vanilla TS + Rust ZMQ bridge | `tauri-app/` |
| Desktop shell B (new) | Tauri **2 stable** + Leptos **0.7** (CSR WASM) + pnpm | `GAINS/gains/`, `GAINS/tauri-app/` |
| Event bus | ZeroMQ PUB/SUB on `tcp://localhost:5555` | `services/bus/hub.py` |
| ASR | `faster-whisper` `base.en` int8, optional CTranslate2 4.5 CUDA | `services/asr/server.py` |
| Vision | MediaPipe `solutions.face_mesh` (legacy API), OpenCV capture | `services/vision/nod.py` |
| TTS | Piper import stub → falls back to `say` / `espeak` | `services/tts/voice.py` |
| Notes | Python writer: txt / md / json | `services/notes/exporter.py` |
| Plugins | Each plugin is a long-running Python process on the ZMQ bus; sample uses **`openai.ChatCompletion.create`** (removed in `openai>=1.0`) on `gpt-3.5-turbo` | `GAINS/plugins/grammar_guard/plugin.py` |
| Tests | Three ad-hoc scripts (`test_*.py`) at repo root; no pytest | `test_*.py` |
| CI | One workflow: `tauri-build.yml`, tag-triggered cross-platform build with mac notarisation + Windows signing | `.github/workflows/` |

---

## 2. What's outdated or risky

### Tauri shell

- **`tauri = 2.0.0-beta.9`** in `tauri-app/src-tauri/Cargo.toml:13-16`. Tauri 2
  went **stable in October 2024**; current line is **2.11.x (Apr 2026)**.
  Beta.9 has known security issues and a different config schema.
- **`tauri.conf.json` uses Tauri v1 `allowlist` syntax** (`tauri-app/tauri.conf.json:14-20`).
  v2 replaced this with **capability files** (`src-tauri/capabilities/*.json`),
  which the newer `GAINS/` tree already uses.
- **Frontend imports** in `tauri-app/src/main.ts:5-6`:
  - `@tauri-apps/api/tauri` (`invoke`) → moved to `@tauri-apps/api/core` in v2.
  - `@tauri-apps/api/updater` → moved to the separate
    **`@tauri-apps/plugin-updater`** crate + JS package in v2.
- **`zmq = "0.3"`** in `tauri-app/src-tauri/Cargo.toml:20` — 0.3 is a 2017-era
  crate. Current is `zmq = "0.10"`. Also: the bridge calls `app_handle.emit_all`
  (`tauri-app/src-tauri/src/zmq_bridge.rs:18`), which is **renamed to `emit`**
  on `AppHandle` in Tauri 2.
- **`browserfs`** and **`zeromq` (npm)** in `GAINS/tauri-app/package.json:13-15`
  are unused by any TS code I found, and `browserfs` is unmaintained (last
  release 2017).
- **`updater.endpoints`** in `GAINS/gains/src-tauri/tauri.conf.json:39` is the
  placeholder `https://your-bucket-or-gh-pages/...`. Auto-updates won't work.
- **CSP `null`** in both shells. Tauri v2 docs recommend a strict default and
  warn about shipping `null`.
- **Two competing Tauri app trees.** Pick one and delete the other (the
  Leptos-on-Tauri-2-stable copy in `GAINS/` is the obvious survivor).

### Python services

- **`openai.ChatCompletion.create`** + `gpt-3.5-turbo` in
  `GAINS/plugins/grammar_guard/plugin.py:18-23`. Removed in **openai-python
  1.0** (Nov 2023). Will not run against current `pip install openai`. Model
  itself is superseded by `gpt-4.1-mini` / `gpt-5-mini` family.
- **`asr/server.py` import bug**: `WhisperModel` and the `device` / `compute`
  variables are referenced (`GAINS/services/asr/server.py:27-34`) but never
  imported or defined. The CUDA / CT2 branch can't currently run.
- **MediaPipe `mp.solutions.face_mesh`** (`services/vision/nod.py:16-20`) is
  the **legacy Solutions API**. Google replaced it in 2023 with
  **MediaPipe Tasks** (`mediapipe.tasks.python.vision.FaceLandmarker`), which
  also gives **blendshapes and 3D transformation matrices** — exactly what a
  nod/head-pose detector wants, without hand-rolled pitch math.
- **Piper TTS branch never executes** — the `try` block immediately raises
  `ImportError` (`services/tts/voice.py:9-13`). It's effectively a stub that
  always falls back to `say` / `espeak`.
- **`ctranslate2==4.5.0`** in CI is pinned old; current is 4.6+.
- **No `requirements.txt` / `pyproject.toml`.** Python deps are implicit.
- **No structured logging.** `print()` everywhere, with emoji decoration that
  makes log scraping painful.
- **`sounddevice.RawInputStream(..., blocksize=1024)` + a callback that runs
  `model.transcribe()` synchronously** (`services/asr/server.py:44-72`). This
  is unsafe — running heavy ML in the audio callback can drop frames. Should
  use a queue + worker thread.

### Event bus / IPC

- **ZeroMQ PUB/SUB on a single port** with no topic prefixes used as
  filters (every subscriber sets `setsockopt_string(zmq.SUBSCRIBE, "")` and
  filters in Python). Loses the main reason to use ZMQ pub/sub.
- **No event schema.** The payload shape is ad-hoc JSON; the wire contract
  drifts silently between Python publishers and the Rust bridge.
- **PUB/SUB is lossy on slow joiners** — the Rust bridge can miss messages
  during startup. There's no ack channel.

### Build / CI / quality

- **Single workflow, tag-triggered only.** No PR CI, no `cargo test`, no
  `pytest`, no `cargo clippy`, no type-check, no lint.
- **`pnpm/action-setup@v2`** is two majors old (current: v4).
- **`actions/upload-artifact@v4`** is fine.
- **`brew install notarytool`** is wrong — `notarytool` ships with Xcode CLT,
  not Homebrew; this step would no-op or fail.
- **No SBOM / `cargo deny` / `pip-audit`.** No supply-chain checks.
- **No `.editorconfig`, `rustfmt.toml`, `ruff`/`black` config.**
- **Three test scripts at repo root** (`test_services.py`, `test_sprint2.py`,
  `test_zmq_bridge.py`) — really import smoke tests, not pytest.

---

## 3. Modernization options (ranked by leverage)

### A. Pick a target shell and delete the rest *(half a day)*

Keep `GAINS/gains/` (Tauri 2 stable + Leptos 0.7) as the canonical shell.
Delete `tauri-app/` and `GAINS/tauri-app/`. Today the repo carries three
half-built shells at three different Tauri versions.

### B. Land Tauri 2.11 + the v2 plugin ecosystem *(1–2 days)*

- Bump `tauri` / `tauri-build` to **`2`** (currently 2.11.x).
- Bump `leptos` to **`0.8`** (current 0.8.19, Apr 2026); the `app.rs` you have
  is already 0.7-style and ports cleanly.
- Replace `@tauri-apps/api/tauri` → `@tauri-apps/api/core`.
- Add `tauri-plugin-updater` (Rust + JS) and a real `updater.endpoints` URL,
  generate a real `pubkey`, and gate behind `updater:default` capability.
- Add `tauri-plugin-shell` for any sidecar use.
- Tighten `security.csp` to a real policy.
- Drop `browserfs` and the `zeromq` npm dep — both unused.

### C. Replace the Python services with native Rust *(1–2 weeks, the biggest win)*

This is the single largest leverage point. Everything Python is doing has a
mature Rust crate today. Eliminating Python kills the ZMQ bus, the PyInstaller
sidecar dance, and the cross-language wire schema all at once.

| Today (Python) | Native Rust replacement |
|---|---|
| `faster-whisper` + `ctranslate2` | **`whisper-rs`** (whisper.cpp 1.7 bindings, CUDA/Metal/Vulkan/CoreML) or **`sherpa-rs`** for Parakeet / Moonshine streaming |
| `mediapipe.solutions.face_mesh` | **`ort`** (ONNX Runtime) + the **FaceLandmarker** `.task` model, or `mediapipe-rs` |
| `piper` Python (broken) | **`sherpa-onnx`** Rust crate — supports Piper VITS models out of the box; or `piper-rs` |
| `openai.ChatCompletion` in plugin | **`async-openai`** crate (or call directly via `reqwest`) using the **Responses API** |
| `zmq` pub/sub | `tokio::sync::broadcast` channels — same fan-out semantics, in-process, typed |
| Note exporter | Plain Rust + `serde_json` / a small markdown writer |

If you want a soft landing instead of a rewrite, use **Tauri sidecars**:
ship the Python services as PyInstaller binaries under `externalBin`, started
by `tauri-plugin-shell` with stdin/stdout JSON-lines. That gets you proper
process lifecycle and lets you delete the manual ZMQ bridge.

### D. Pick a better ASR than `base.en` *(half a day after C)*

The 2026 STT landscape is no longer Whisper-only:

- **NVIDIA Parakeet TDT 0.6 / 1.1B** — fastest on the Open ASR leaderboard,
  ~6.5× faster than Canary, real-time on CPU. Great default for English
  dictation.
- **NVIDIA Canary Qwen 2.5B** — top of leaderboard for English accuracy (~5.6%
  WER), worth it when accuracy matters more than latency.
- **Moonshine v2** — purpose-built for low-latency edge dictation, beats
  Whisper-large-v3 on English with ~6× fewer params. Strong fit for a
  desktop "speak-and-nod" app.
- **Whisper large-v3-turbo** / **distil-large-v3** — keep these for the
  multilingual story; they're 6× faster than large-v3 within 1% WER.

All four are available as ONNX/GGUF and run through `sherpa-onnx` or
`whisper-rs`. None require Python at runtime.

### E. Modernise the vision pipeline *(1 day)*

Switch to **MediaPipe Tasks `FaceLandmarker`**: it returns a 4×4
**facial-transformation matrix** and 52 blendshapes per frame. Pitch comes
straight out of the matrix — no more `arctan2(nose.z, nose.y)` heuristic — and
you get `mouth_open`, `eye_blink_left/right`, `brow_down` etc. for free, which
opens up a much richer gesture vocabulary than "nod commits".

### F. Fix the plugin system *(2–3 days)*

The current "every plugin is a long-running Python process subscribed to ZMQ"
model is heavy and language-locked. Replace with **Extism + Wasmtime**:

- Plugins ship as `.wasm` modules (Rust, Go, JS, Python via Pyodide-wasm, etc.).
- Host (Rust) loads them via `extism` crate, exposes a small typed host API
  (`emit_event`, `read_event`, `http_fetch`, `llm_call`).
- Sandboxed: no filesystem / network unless the host grants it.

This makes plugins safe to install from third parties, removes the Python
runtime requirement on the user's machine, and gives you a real plugin
registry path.

### G. Tighten the event protocol *(1 day)*

- Define events in one place — a **`.proto`** or **`schemars` JSON-Schema**
  file under `crates/events/` — and generate types for Rust + TS (+ Python if
  kept).
- Use a **typed channel** (`tokio::sync::broadcast<Event>`) instead of stringly
  JSON.
- Add a monotonic `seq` field and a small ring buffer so late subscribers can
  replay the last N events on connect (fixes the PUB/SUB slow-joiner problem).

### H. CI + quality bar *(1 day)*

- **PR workflow**: `cargo fmt --check`, `cargo clippy -D warnings`,
  `cargo test`, `pnpm typecheck`, `pnpm build`, `pytest` (if Python is kept).
- **Supply chain**: `cargo deny check`, `pip-audit`, `pnpm audit --prod`,
  Dependabot or Renovate.
- **Release**: keep the existing tag-triggered build; bump
  `pnpm/action-setup` to v4; fix the `brew install notarytool` line.
- Add `rustfmt.toml`, `ruff` config, `.editorconfig`.
- Replace the three `test_*.py` smoke scripts with `pytest` under `tests/`.

### I. Distribution polish *(half a day)*

- Real updater endpoint (CrabNebula Cloud, GitHub Releases via
  `tauri-action`, or self-hosted `latest.json`).
- Sign and notarise via the existing CI steps (the workflow is already set
  up for it — just needs working secrets and the `notarytool` fix).
- Ship Apple Silicon + Intel universal DMG, MSI, deb/AppImage. Add Linux
  Flatpak for the Steam-Deck / immutable-distro crowd.

---

## 4. Suggested execution order

1. **Cleanup** — pick `GAINS/gains/` as the one true tree; delete the
   duplicate `tauri-app/` and `GAINS/tauri-app/` directories; move the three
   `test_*.py` scripts under `tests/` and convert to pytest.
2. **Tauri/Leptos bump** — 2.11 + Leptos 0.8 + updater plugin + capability
   tightening + working CSP.
3. **Plug the openai-python 1.x + missing-import bugs** in the existing
   Python services so the current architecture at least runs end-to-end on a
   fresh install. This buys a checkpoint to demo from.
4. **Native ASR + TTS via `sherpa-onnx` (Rust)**, replacing the ASR and TTS
   Python services. Keep the vision service in Python for one more iteration.
5. **Native vision via `ort` + MediaPipe Tasks FaceLandmarker `.task`**
   model. Now Python is gone from the runtime path.
6. **Delete the ZMQ bridge**, switch event bus to `tokio::broadcast<Event>`
   with a typed event schema crate.
7. **Plugin system → Extism/Wasmtime.** Port `grammar_guard` to Rust-WASM as
   the first sample.
8. **CI hardening + real updater endpoint + signed releases.**

Steps 1–3 are roughly a week; 4–6 are the rewrite proper (2–3 weeks); 7–8 are
another week.

---

## 5. Sources

- Tauri 2 stable / current 2.11.x release line — <https://v2.tauri.app/release/>, <https://github.com/tauri-apps/tauri/releases>
- Tauri v2 sidecar pattern — <https://v2.tauri.app/develop/sidecar/>
- Tauri v2 updater plugin — <https://v2.tauri.app/plugin/updater/>
- Leptos 0.8.19 release — <https://docs.rs/crate/leptos/latest>
- OpenAI Python SDK v1 migration (ChatCompletion removed) — <https://github.com/openai/openai-python/discussions/742>
- MediaPipe Tasks FaceLandmarker — <https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker>
- 2026 STT landscape (Parakeet / Canary / Moonshine / Whisper) — <https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks>, <https://www.onresonant.com/resources/local-stt-models-2026>
- whisper.cpp / whisper-rs — <https://github.com/ggml-org/whisper.cpp>, <https://github.com/tazz4843/whisper-rs>
- sherpa-onnx Piper TTS — <https://k2-fsa.github.io/sherpa/onnx/tts/piper.html>
- Extism / Wasmtime plugin system — <https://extism.org/docs/concepts/plug-in-system/>
- Whisper variants comparison — <https://modal.com/blog/choosing-whisper-variants>
