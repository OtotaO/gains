"""ASR service: streaming faster-whisper transcription.

Reads settings.yaml for language + model size, runs inference on a worker
thread (NOT inside the sounddevice callback — that previously risked
dropping audio frames when transcription took longer than a block).
Publishes ``asr.partial`` events with confidence + word-level timestamps.

Bug fixes vs. previous version:
* CT2 / multi-language path referenced undefined ``WhisperModel`` /
  ``device`` / ``compute`` symbols.
* The confidence gate was ``avg_logprob > 0.7``; Whisper log-probs are
  negative, so the gate was unsatisfiable. Switched to ``> min_avg_logprob``
  (default ``-0.7`` ≈ 50% confidence).
* Heavy ``model.transcribe`` ran in the audio callback; now in a worker.
* Publisher now connects to the bus' XSUB side (5556) instead of the
  PUB-bound 5555, which previously dropped every message.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import yaml
import zmq
from faster_whisper import WhisperModel

log = logging.getLogger("gains.asr")

CONFIG_PATH = Path(__file__).parent / "config" / "settings.yaml"
EN_ONLY_SIZES = {"tiny", "base", "small", "medium"}

DEFAULTS: dict[str, Any] = {
    "asr_language": "en",
    "asr_model": "small",
    "beam_size": 5,
    "best_of": 5,
    "min_avg_logprob": -0.7,
    "silence_timeout_sec": 8.0,
    "vad_filter": True,
    "vad_min_silence_ms": 500,
    "vad_speech_pad_ms": 400,
    "sample_rate": 16000,
    "block_ms": 64,
}


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open() as f:
            user = yaml.safe_load(f) or {}
        cfg.update({k: v for k, v in user.items() if v is not None})
    return cfg


def resolve_model_name(size: str, lang: str) -> str:
    if lang == "en" and size in EN_ONLY_SIZES:
        return f"{size}.en"
    return size


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = load_config()
    lang = cfg["asr_language"]
    model_name = resolve_model_name(cfg["asr_model"], lang)

    device = "cuda" if os.getenv("DEVICE") == "gpu" else "cpu"
    compute = "float16" if device == "cuda" else "int8"
    log.info("loading whisper model=%s device=%s compute=%s", model_name, device, compute)
    model = WhisperModel(model_name, device=device, compute_type=compute)

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://localhost:5556")

    audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=8)
    stop = threading.Event()
    is_listening = threading.Event()
    last_speech = [time.monotonic()]  # list-as-cell for nonlocal-ish mutation

    def silence_watchdog() -> None:
        while not stop.is_set():
            time.sleep(0.5)
            if (is_listening.is_set()
                    and (time.monotonic() - last_speech[0]) > cfg["silence_timeout_sec"]):
                pub.send_json({"event": "tts.play", "text": "Are you done?", "ts": time.time()})
                last_speech[0] = time.monotonic()

    def transcribe_worker() -> None:
        min_lp = cfg["min_avg_logprob"]
        # For .en models we don't pass language; otherwise pass the configured one.
        explicit_lang = None if model_name.endswith(".en") else lang
        while not stop.is_set():
            try:
                samples = audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                segments, _info = model.transcribe(
                    samples,
                    language=explicit_lang,
                    vad_filter=cfg["vad_filter"],
                    vad_parameters={
                        "min_silence_duration_ms": cfg["vad_min_silence_ms"],
                        "speech_pad_ms": cfg["vad_speech_pad_ms"],
                    },
                    beam_size=cfg["beam_size"],
                    best_of=cfg["best_of"],
                    word_timestamps=True,
                )
                for seg in segments:
                    if not seg.text.strip() or seg.avg_logprob < min_lp:
                        continue
                    last_speech[0] = time.monotonic()
                    is_listening.set()
                    pub.send_json({
                        "event": "asr.partial",
                        "text": seg.text,
                        "ts": time.time(),
                        "confidence": seg.avg_logprob,
                        "start": seg.start,
                        "end": seg.end,
                        "words": [
                            {"word": w.word, "start": w.start, "end": w.end}
                            for w in (seg.words or [])
                        ],
                    })
            except Exception:
                log.exception("transcription failed")

    threading.Thread(target=silence_watchdog, daemon=True).start()
    threading.Thread(target=transcribe_worker, daemon=True).start()

    block = int(cfg["sample_rate"] * cfg["block_ms"] / 1000)

    def callback(indata: np.ndarray, _frames: int, _time_info: Any, status: sd.CallbackFlags) -> None:
        if status:
            log.debug("audio status: %s", status)
        try:
            audio_q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            log.warning("audio queue full, dropping block")

    log.info("listening: lang=%s model=%s beam=%d", lang, model_name, cfg["beam_size"])
    try:
        with sd.InputStream(
            samplerate=cfg["sample_rate"],
            channels=1,
            dtype="float32",
            callback=callback,
            blocksize=block,
        ):
            while not stop.is_set():
                time.sleep(0.1)
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        stop.set()
        pub.close()
        ctx.term()


if __name__ == "__main__":
    main()
