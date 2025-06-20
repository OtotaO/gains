from faster_whisper import WhisperModel
import zmq, sounddevice as sd, numpy as np, time, threading

ctx, pub = zmq.Context(), zmq.Context().socket(zmq.PUB)
pub.connect("tcp://localhost:5555")

# ASR Configuration - Sprint 2 accuracy tuning
ASR_CONFIG = {
    "model_size": "base.en",  # Options: tiny, base, small, medium, large
    "compute_type": "int8",   # Options: int8, float16, float32
    "beam_size": 5,           # Beam search for better accuracy
    "best_of": 5,             # Number of candidates to consider
    "vad_filter": True,       # Voice activity detection
    "vad_parameters": {
        "min_silence_duration_ms": 500,
        "speech_pad_ms": 400
    }
}

model = WhisperModel(
    ASR_CONFIG["model_size"], 
    compute_type=ASR_CONFIG["compute_type"]
)

# Silence timeout tracking
last_speech_time = time.time()
silence_timeout = 8.0  # 8 seconds
is_listening = False
confidence_threshold = 0.7  # Minimum confidence for transcription

def check_silence_timeout():
    """Check for silence timeout and trigger TTS if needed"""
    global last_speech_time, is_listening
    while True:
        if is_listening and (time.time() - last_speech_time) > silence_timeout:
            pub.send_json({"event": "tts.play", "text": "Are you done?"})
            last_speech_time = time.time()  # Reset timer
        time.sleep(1)

# Start silence timeout thread
silence_thread = threading.Thread(target=check_silence_timeout, daemon=True)
silence_thread.start()

def callback(indata, *_):
    global last_speech_time, is_listening
    samples = indata[:,0].copy()
    
    # Enhanced transcription with accuracy tuning
    segments, info = model.transcribe(
        samples, 
        vad_filter=ASR_CONFIG["vad_filter"],
        vad_parameters=ASR_CONFIG["vad_parameters"],
        beam_size=ASR_CONFIG["beam_size"],
        best_of=ASR_CONFIG["best_of"],
        word_timestamps=True
    )
    
    for s in segments:
        if s.text.strip() and s.avg_logprob > confidence_threshold:
            last_speech_time = time.time()
            is_listening = True
            
            # Enhanced message with confidence and timing info
            pub.send_json({
                "event": "asr.partial", 
                "text": s.text, 
                "ts": s.end,
                "confidence": s.avg_logprob,
                "start": s.start,
                "end": s.end,
                "words": [{"word": w.word, "start": w.start, "end": w.end} for w in s.words] if s.words else []
            })

print(f"ASR Service Started - Model: {ASR_CONFIG['model_size']}, Beam Size: {ASR_CONFIG['beam_size']}")

with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16",
                       callback=callback, blocksize=1024):
    sd.sleep(10_000_000) 