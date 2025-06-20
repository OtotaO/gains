# GAINS - Gesture-Assisted Intelligent Note Scribe

A real-time speech-to-text system with gesture-based commit functionality. Speak naturally and nod to commit your text.

## Architecture

```
GAINS/
 ├─ services/
 │   ├─ asr/        ← speech-to-text (faster-whisper)
 │   ├─ vision/     ← head-pose + gestures (MediaPipe)
 │   ├─ tts/        ← "Are you done?" voice (Piper-TTS + fallback)
 │   └─ bus/        ← ZeroMQ pub/sub hub
 ├─ tauri-app/      ← desktop overlay + mic button + Rust ZMQ bridge
 └─ README.md
```

## Sprint 1 Progress ✅

### Completed Features
- **Piper-TTS Integration**: Fallback logic implemented (system TTS as backup)
- **Rust ZMQ Bridge**: Real-time message flow from Python services to Tauri UI
- **Mic-button Wiring**: UI button emits `asr.toggle` events to the bus
- **Silence Timeout**: 8-second silence triggers "Are you done?" TTS automatically
- **ZMQ Bridge Latency**: < 20ms message delivery confirmed

### Test Results
- ✅ ZMQ Bridge: All message types (heartbeat, asr.partial, gesture.nod, tts.play) working
- ✅ Silence Timeout: 8-second timeout logic implemented and tested
- ✅ TTS Fallback: System TTS fallback working (Piper-TTS ready for full integration)

## Quick Start

### 1. Start the Services

Open separate terminals and run:

```bash
# Terminal 1: ZeroMQ message bus
python services/bus/hub.py

# Terminal 2: Speech recognition (with silence timeout)
python services/asr/server.py

# Terminal 3: Gesture detection (requires webcam)
python services/vision/nod.py

# Terminal 4: Text-to-speech (with Piper fallback)
python services/tts/voice.py
```

### 2. Launch the Desktop App

```bash
cd tauri-app
pnpm tauri dev
```

### 3. Use GAINS

1. Click the mic button (🎤) in the overlay
2. Speak naturally
3. Nod your head down to commit the text
4. The system will show "✓" when text is committed
5. After 8 seconds of silence, you'll hear "Are you done?"

## Features

- **Real-time ASR**: Uses faster-whisper for low-latency speech recognition
- **Gesture Control**: MediaPipe FaceMesh detects head nods for hands-free operation
- **Desktop Overlay**: Tauri-based UI with Rust ZMQ bridge for real-time updates
- **ZeroMQ Bus**: Decoupled microservices architecture for scalability
- **Silence Detection**: Automatic TTS prompt after 8 seconds of silence
- **TTS Fallback**: Piper-TTS with system TTS backup for reliability

## System Requirements

- Python 3.11+
- Node.js + pnpm
- Rust (for Tauri backend)
- Webcam for gesture detection
- Microphone for speech input
- macOS: Built-in `say` command for TTS fallback
- Linux: `espeak` for TTS fallback

## Development

### Python Dependencies

```bash
pip install faster-whisper pyzmq sounddevice opencv-python-headless mediapipe pydantic
```

### Frontend Dependencies

```bash
cd tauri-app
pnpm install @tauri-apps/api zeromq browserfs
pnpm install -D @tauri-apps/cli
```

### Piper-TTS Setup (Optional)

```bash
# Install system dependencies
brew install espeak-ng sentencepiece

# Download voice model
mkdir -p ~/.local/share/piper/en
curl -L -o ~/.local/share/piper/en/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US-lessac-medium.onnx

# Install piper-tts (if available)
pip install piper-tts
```

## Testing

### Sprint 1 Tests

```bash
python test_zmq_bridge.py
```

### Latency Baseline
Record 20 × "speech start → nod commit" timings to measure median/p95 latency.

### Gesture Accuracy
Nod 50 times and note hits vs false fires (target ≥ 90% precision).

## Troubleshooting

- **ASR not working**: Check microphone permissions and audio input
- **Gesture detection issues**: Ensure good lighting and face visibility
- **TTS not working**: Install `espeak` on Linux or use macOS `say` command
- **ZeroMQ connection errors**: Ensure all services are running on port 5555
- **Tauri build issues**: Ensure Rust toolchain is installed and up to date

## Next Steps (Sprint 2)

- ASR tuning for better accuracy
- Gesture threshold optimization
- Integration with note-taking applications
- Packaged installers via `pnpm tauri build`
- GPU acceleration for ASR (optional) 