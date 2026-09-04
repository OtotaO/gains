# GAINS — Gesture-Assisted Intelligent Note Scribe

GAINS is a multi-modal note-taking app: you **speak**, and **nod** to commit
what you just said. Speech goes through Whisper, head pose through a
MediaPipe Tasks pipeline, and committed text flows through a plug-in chain
(e.g. `sample_rewriter`) before landing in your notes. Speech recognition,
head pose and TTS run entirely on-device. Plug-ins may not: the bundled
`grammar_guard` plug-in sends committed text to OpenAI, and is only active
if you set `OPENAI_API_KEY`.

## Architecture

```
┌──────────────────────┐    ┌───────────────────────────────────────┐
│ Tauri 2 + Leptos 0.8 │    │   ZeroMQ bus (XSUB/XPUB proxy)       │
│  (Rust desktop UI)   │───▶│   publishers connect → tcp://*:5556  │
│   listens on 5555    │◀───│   subscribers connect → tcp://*:5555 │
└──────────────────────┘    └───────────────────────────────────────┘
                                       ▲ ▲ ▲ ▲ ▲
                ┌──────────────────────┘ │ │ │ └──────────────────────┐
                │            ┌───────────┘ │ └───────────┐            │
                ▼            ▼             ▼             ▼            ▼
        ┌──────────┐  ┌────────────┐ ┌───────────┐  ┌─────────┐ ┌─────────┐
        │ services │  │ services/  │ │ services/ │  │ plugins/│ │ services│
        │   /asr   │  │   vision   │ │    tts    │  │ /grammar│ │ /notes  │
        │ (faster- │  │ (Mediapipe │ │  (Piper)  │  │  _guard │ │ writer  │
        │ whisper) │  │  Tasks)    │ │           │  │  /sample│ │         │
        └──────────┘  └────────────┘ └───────────┘  └─────────┘ └─────────┘
```

Events flowing on the bus:

| Topic            | Payload                                          | Producer        |
|------------------|--------------------------------------------------|-----------------|
| `heartbeat`      | `{ts}`                                           | bus             |
| `asr.partial`    | `{text, ts, confidence, start, end, words[]}`    | asr             |
| `gesture.nod`    | `{ts, pitch_deg}`                                | vision          |
| `text.committed` | `{text, ts}`                                     | Tauri shell     |
| `plugin.rewrite` | `{text, orig_ts, plugin, ts}`                    | any plug-in     |
| `tts.play`       | `{text, ts}`                                     | asr (silence)   |

## Quick start

```bash
# Python (3.11+) — pick the dep groups you need
pip install -e ".[asr,vision,tts,plugins,dev]"

# Run the services (each in its own terminal)
gains-bus            # XSUB/XPUB proxy on 5555 / 5556
gains-asr            # streaming whisper transcription
gains-vision         # MediaPipe Tasks head pose
gains-tts            # piper TTS with platform fallback
gains-notes          # txt/md/json export
gains-plugins        # plug-in runner

# Desktop shell (Tauri 2 + Leptos 0.8)
cd tauri-app
cargo install --locked trunk
cargo install tauri-cli --version "^2" --locked
cargo tauri dev
```

## Configuration

`services/asr/config/settings.yaml`:

```yaml
asr_language: en          # ISO-639-1 code
asr_model: small          # tiny / base / small / medium / large-v3 / large-v3-turbo / distil-large-v3
```

For GPU acceleration set `DEVICE=gpu` (uses CTranslate2 + CUDA float16).

For the grammar-guard plugin, set `OPENAI_API_KEY` and optionally
`GRAMMAR_GUARD_MODEL` (default `gpt-4o-mini`).

## Plug-ins

Drop a Python module at `plugins/<name>/plugin.py` that:

1. Subscribes to `tcp://localhost:5555` (bus XPUB side).
2. Reads JSON messages; acts on `text.committed`.
3. Publishes back on `tcp://localhost:5556` (XSUB side) with an event of
   shape `{"event": "plugin.rewrite", "text": ..., "plugin": "<name>", ...}`.

The note exporter splices `plugin.rewrite` payloads into the session in
place of the original ASR text. See `plugins/sample_rewriter/plugin.py`
for a 30-line template, and `docs/plugins.md` for the full reference.

## Development

```bash
# Python lint + tests
ruff check .
pytest

# Rust backend
cd tauri-app/src-tauri
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo check

# Leptos WASM frontend
cd tauri-app
cargo check -p gains-ui --target wasm32-unknown-unknown
```

The `ci.yml` workflow runs all of the above on every PR.

## Modernization status

See `docs/modernization-assessment.md` for the full architectural audit and
roadmap. As of branch `claude/assess-modernization-61ThF`:

* Phase 1 (this branch) — repository consolidation, Python service bug
  fixes, openai-python v1 migration, MediaPipe Tasks migration, Tauri 2 /
  Leptos 0.8 upgrade, updater plugin wired up, PR-CI introduced.
* Phase 2 (future) — replace Python services with native Rust crates
  (`whisper-rs` / `sherpa-onnx` / `ort` + MediaPipe Tasks `.task` model)
  so the runtime ships with zero Python dependency.
* Phase 3 (future) — replace per-plug-in subprocess model with WASM
  plug-ins via Extism + Wasmtime.
