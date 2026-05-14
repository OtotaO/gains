"""TTS service: Piper neural TTS with platform fallback.

Subscribes to ``tts.play`` events on the bus and speaks them. Auto-downloads
a default Piper voice (en_US-amy-medium) to ``~/.gains_models/piper`` on
first run.

Bug fixes vs. previous version:
* The Piper branch unconditionally raised ImportError, so the service
  always silently fell back to ``say``/``espeak``. Now actually loads Piper
  via ``piper-tts`` and only falls back on real failure.
* Subscriber was reading raw JSON instead of filtering for the right event.
* Windows fallback added.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path
from typing import TYPE_CHECKING

import zmq

if TYPE_CHECKING:
    from piper.voice import PiperVoice  # noqa: F401

log = logging.getLogger("gains.tts")

VOICE_DIR = Path.home() / ".gains_models" / "piper"
VOICE_NAME = "en_US-amy-medium"
VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium"


def ensure_voice() -> tuple[Path, Path] | None:
    onnx = VOICE_DIR / f"{VOICE_NAME}.onnx"
    cfg = VOICE_DIR / f"{VOICE_NAME}.onnx.json"
    if onnx.exists() and cfg.exists():
        return onnx, cfg
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        log.info("downloading piper voice to %s", VOICE_DIR)
        urllib.request.urlretrieve(f"{VOICE_BASE}/{VOICE_NAME}.onnx", onnx)
        urllib.request.urlretrieve(f"{VOICE_BASE}/{VOICE_NAME}.onnx.json", cfg)
        return onnx, cfg
    except Exception:
        log.exception("piper voice download failed; falling back to platform TTS")
        return None


_piper_voice = None


def piper_synth(text: str) -> Path | None:
    """Synthesize via piper-tts; cache the loaded voice for reuse."""
    global _piper_voice
    try:
        from piper.voice import PiperVoice
    except ImportError:
        return None
    if _piper_voice is None:
        paths = ensure_voice()
        if not paths:
            return None
        onnx_path, _ = paths
        try:
            _piper_voice = PiperVoice.load(str(onnx_path))
        except Exception:
            log.exception("failed to load piper voice")
            return None
    fd, name = tempfile.mkstemp(suffix=".wav")
    Path(name).touch()  # ensure file exists before piper opens it
    try:
        with wave.open(name, "wb") as wf:
            _piper_voice.synthesize(text, wf)
        return Path(name)
    finally:
        import os
        os.close(fd)


def platform_speak(text: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["say", text], check=False)
    elif sys.platform.startswith("linux"):
        if shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", text], check=False)
        elif shutil.which("espeak"):
            subprocess.run(["espeak", text], check=False)
        else:
            log.warning("no platform TTS available (install espeak-ng)")
    elif sys.platform == "win32":
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
        )
        subprocess.run(["powershell", "-Command", ps], check=False)


def play_wav(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["afplay", str(path)], check=False)
    elif shutil.which("aplay"):
        subprocess.run(["aplay", "-q", str(path)], check=False)
    elif shutil.which("paplay"):
        subprocess.run(["paplay", str(path)], check=False)
    elif sys.platform == "win32":
        ps = f'(New-Object Media.SoundPlayer "{path}").PlaySync()'
        subprocess.run(["powershell", "-Command", ps], check=False)


def speak(text: str) -> None:
    wav = piper_synth(text)
    if wav is not None:
        try:
            play_wav(wav)
        finally:
            wav.unlink(missing_ok=True)
        return
    platform_speak(text)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://localhost:5555")
    sub.setsockopt_string(zmq.SUBSCRIBE, "")
    log.info("tts service ready")
    try:
        while True:
            msg = sub.recv_json()
            if msg.get("event") != "tts.play":
                continue
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            log.info("speaking: %s", text[:60])
            speak(text)
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        ctx.term()


if __name__ == "__main__":
    main()
