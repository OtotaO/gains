import cv2, mediapipe as mp, numpy as np, zmq, time, collections

ctx, pub = zmq.Context(), zmq.Context().socket(zmq.PUB)
pub.connect("tcp://localhost:5555")

# Gesture Configuration - Sprint 2 precision tuning
GESTURE_CONFIG = {
    "nod_threshold": -15.0,      # Degrees for nod detection (was -17)
    "motion_smoothing": 5,       # Frames to average for smooth motion
    "cooldown_period": 1.0,      # Seconds between nod detections
    "confidence_threshold": 0.8,  # Minimum face detection confidence
    "min_face_size": 0.1,        # Minimum face size in frame
    "motion_threshold": 2.0,     # Minimum motion to trigger detection
}

mesh = mp.solutions.face_mesh.FaceMesh(
    refine_landmarks=True,
    min_detection_confidence=GESTURE_CONFIG["confidence_threshold"],
    min_tracking_confidence=GESTURE_CONFIG["confidence_threshold"]
)

cap = cv2.VideoCapture(0)

# Motion tracking for precision
pitch_history = collections.deque(maxlen=GESTURE_CONFIG["motion_smoothing"])
last_nod_time = 0
last_pitch = None

def detect_nod(current_pitch, timestamp):
    """Enhanced nod detection with motion analysis"""
    global last_nod_time, last_pitch
    
    # Add to history for smoothing
    pitch_history.append(current_pitch)
    
    # Wait for enough history
    if len(pitch_history) < GESTURE_CONFIG["motion_smoothing"]:
        return False
    
    # Check cooldown period
    if timestamp - last_nod_time < GESTURE_CONFIG["cooldown_period"]:
        return False
    
    # Calculate smoothed pitch
    smoothed_pitch = np.mean(pitch_history)
    
    # Check for significant downward motion
    if last_pitch is not None:
        motion = last_pitch - smoothed_pitch
        if (motion > GESTURE_CONFIG["motion_threshold"] and 
            smoothed_pitch < GESTURE_CONFIG["nod_threshold"]):
            last_nod_time = timestamp
            return True
    
    last_pitch = smoothed_pitch
    return False

print(f"Vision Service Started - Nod Threshold: {GESTURE_CONFIG['nod_threshold']}°, Smoothing: {GESTURE_CONFIG['motion_smoothing']} frames")

while cap.isOpened():
    ok, frame = cap.read()
    if not ok: 
        break
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = mesh.process(rgb)
    
    if res.multi_face_landmarks:
        face_landmarks = res.multi_face_landmarks[0]
        
        # Get nose position (landmark 1)
        nose = face_landmarks.landmark[1]
        
        # Calculate pitch angle
        pitch = np.degrees(np.arctan2(nose.z, nose.y))
        
        # Enhanced nod detection
        if detect_nod(pitch, time.time()):
            pub.send_json({
                "event": "gesture.nod",
                "ts": time.time(),
                "pitch": pitch,
                "confidence": nose.z  # Use z-coordinate as confidence
            })
            print(f"Nod detected! Pitch: {pitch:.1f}°")
    
    if cv2.waitKey(1) == 27: 
        break

cap.release()
cv2.destroyAllWindows() 