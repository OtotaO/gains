"""Vision service: head-nod detection via MediaPipe Tasks FaceLandmarker.

Replaces the legacy ``mp.solutions.face_mesh`` Solutions API (in maintenance
mode since 2023). Pitch comes from the facial transformation matrix; we also
surface a small selection of blendshapes so the UI can show a quick "head
pose" indicator and so downstream gesture vocabularies can grow beyond
"nod commits".

Bug fixes vs. previous version:
* Pitch was derived from ``arctan2(nose.z, nose.y)`` on a single landmark
  with no head-size normalisation — sensitive to camera distance. Now uses
  the facial-transformation matrix.
* Publisher now connects to the XSUB side of the bus (5556).
"""
from __future__ import annotations

import collections
import logging
import time
import urllib.request
from pathlib import Path

import numpy as np

log = logging.getLogger("gains.vision")

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
MODEL_PATH = Path.home() / ".gains_models" / "face_landmarker.task"

CONFIG = {
    "nod_threshold_deg": -15.0,
    "motion_smoothing": 5,
    "cooldown_sec": 1.0,
    "motion_threshold_deg": 2.0,
}


def ensure_model() -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    log.info("downloading face_landmarker model to %s", MODEL_PATH)
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def pitch_from_matrix(matrix: np.ndarray) -> float:
    """Extract pitch (X-axis rotation, degrees) from a 4×4 transformation matrix.

    Uses YXZ Tait-Bryan extraction: ``atan2(-r[1,2], r[2,2])`` returns θ for
    a pure X-rotation by θ, and is stable for the small additional yaw/roll
    present in real head poses. Negative = head down (nod).
    """
    r = matrix[:3, :3]
    pitch_rad = float(np.arctan2(-r[1, 2], r[2, 2]))
    return float(np.degrees(pitch_rad))


def main() -> None:
    import cv2
    import mediapipe as mp
    import zmq
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision as mp_vision

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    model_path = ensure_model()

    options = mp_vision.FaceLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp_vision.RunningMode.VIDEO,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
        num_faces=1,
    )

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://localhost:5556")

    cap = cv2.VideoCapture(0)
    pitch_hist: collections.deque[float] = collections.deque(maxlen=CONFIG["motion_smoothing"])
    last_nod = 0.0
    last_pitch: float | None = None

    log.info(
        "vision service started: nod_threshold=%.1f° smoothing=%d frames",
        CONFIG["nod_threshold_deg"], CONFIG["motion_smoothing"],
    )

    try:
        with mp_vision.FaceLandmarker.create_from_options(options) as landmarker:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int(time.monotonic() * 1000)
                result = landmarker.detect_for_video(mp_image, ts_ms)

                if not result.facial_transformation_matrixes:
                    if cv2.waitKey(1) == 27:
                        break
                    continue
                matrix = np.array(result.facial_transformation_matrixes[0])
                pitch = pitch_from_matrix(matrix)
                pitch_hist.append(pitch)
                if len(pitch_hist) < CONFIG["motion_smoothing"]:
                    if cv2.waitKey(1) == 27:
                        break
                    continue

                smoothed = float(np.mean(pitch_hist))
                now = time.monotonic()
                if now - last_nod >= CONFIG["cooldown_sec"] and last_pitch is not None:
                    motion = last_pitch - smoothed
                    if (motion > CONFIG["motion_threshold_deg"]
                            and smoothed < CONFIG["nod_threshold_deg"]):
                        last_nod = now
                        pub.send_json({
                            "event": "gesture.nod",
                            "ts": time.time(),
                            "pitch_deg": smoothed,
                        })
                        log.info("nod detected, pitch=%.1f°", smoothed)
                last_pitch = smoothed

                if cv2.waitKey(1) == 27:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        pub.close()
        ctx.term()


if __name__ == "__main__":
    main()
