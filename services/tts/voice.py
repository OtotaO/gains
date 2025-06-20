import zmq, subprocess, tempfile, os

ctx, sub = zmq.Context(), zmq.Context().socket(zmq.SUB)
sub.connect("tcp://localhost:5555"); sub.setsockopt_string(zmq.SUBSCRIBE, "tts.play")

def play_audio_with_piper(text):
    """Try to use Piper-TTS, fallback to system TTS"""
    try:
        import piper
        # Piper-TTS implementation would go here
        # For now, fall back to system TTS
        raise ImportError("Piper not fully configured")
    except ImportError:
        # Fallback to system TTS
        if os.uname().sysname == "Darwin":  # macOS
            subprocess.run(["say", text])
        else:  # Linux
            subprocess.run(["espeak", text])

while True:
    msg = sub.recv_json()
    text = msg["text"]
    play_audio_with_piper(text) 