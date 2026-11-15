"""Local OpenCV acquisition and MediaPipe Tasks landmarks. Frames stay in memory."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from urllib.request import urlopen

from blindspot.models import Observation, Protocol

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
DEFAULT_MODEL = Path("models/hand_landmarker.task")
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


class CameraUnavailable(RuntimeError):
    pass


@dataclass
class CaptureResult:
    frames: list[Observation]
    duration_s: float
    metadata: dict


def prepare_model(path: Path = DEFAULT_MODEL) -> str:
    """Explicit one-time download from Google's versioned model endpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen(MODEL_URL, timeout=30) as response:
            data = response.read(20_000_001)
        if len(data) > 20_000_000 or len(data) < 100_000:
            raise ValueError("Unexpected model size; download rejected")
        temporary = path.with_suffix(".part")
        temporary.write_bytes(data)
        temporary.replace(path)
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        raise ValueError("Model checksum mismatch. Remove the model and prepare it again.")
    return digest


def landmark_distance(points, width: int, height: int) -> float | None:
    if len(points) != 21 or width <= 0 or height <= 0:
        return None
    if any(
        not math.isfinite(p.x)
        or not math.isfinite(p.y)
        or not 0.02 <= p.x <= 0.98
        or not 0.02 <= p.y <= 0.98
        for p in points
    ):
        return None

    def distance(a, b):
        return math.hypot((points[a].x - points[b].x) * width, (points[a].y - points[b].y) * height)

    palm = distance(5, 17)
    if palm < width * 0.03:
        return None
    return distance(4, 8) / palm


def capture(
    policy: Protocol,
    model_path: Path = DEFAULT_MODEL,
    camera_index: int = 0,
    progress: Callable | None = None,
) -> CaptureResult:
    if not model_path.is_file():
        raise CameraUnavailable("Hand model missing. Run: python -m blindspot prepare-camera")
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
    except (ImportError, OSError) as exc:
        raise CameraUnavailable(
            'Camera dependencies unavailable. Install: pip install -e ".[camera]"'
        ) from exc
    cap = cv2.VideoCapture(camera_index)
    try:
        if not cap.isOpened():
            raise CameraUnavailable(
                "Cannot open camera. Close other camera apps, check OS "
                "permissions, or choose another camera index."
            )
        # Request a smaller camera frame to reduce inference and preview overhead.

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        frames: list[Observation] = []
        with vision.HandLandmarker.create_from_options(options) as detector:
            # Short warmup avoids charging model setup time to the measurement.
            start, seq, last_ms = time.monotonic(), 0, -1
            while time.monotonic() - start < policy.duration_s:
                loop = time.monotonic()
                ok, image = cap.read()
                t = time.monotonic() - start
                if t >= policy.duration_s:
                    break
                ratio, rgb = None, None
                if ok and image is not None:
                    height, width = image.shape[:2]
                    if width > 640:
                        scale = 640 / width
                        image = cv2.resize(
                            image,
                            (640, max(1, round(height * scale))),
                            interpolation=cv2.INTER_AREA,
                        )
                    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    # Mirror before inference: handedness follows the selfie-view convention.
                    rgb = cv2.flip(rgb, 1)
                    stamp = max(last_ms + 1, int(t * 1000))
                    last_ms = stamp
                    result = detector.detect_for_video(
                        mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                        stamp,
                    )
                    # Ambiguous/multiple hands are deliberately rejected.
                    if len(result.hand_landmarks) == 1 and result.handedness:
                        label = result.handedness[0][0].category_name
                        if label == policy.hand:
                            points = result.hand_landmarks[0]
                            ratio = landmark_distance(points, image.shape[1], image.shape[0])
                            if ratio is not None:
                                for p in points:
                                    cv2.circle(
                                        rgb,
                                        (int(p.x * image.shape[1]), int(p.y * image.shape[0])),
                                        3,
                                        (0, 150, 180),
                                        -1,
                                    )
                    frames.append(Observation(t, ratio, 1.0 if ratio is not None else 0.0, seq))
                else:
                    frames.append(Observation(t, None, 0.0, seq))
                if progress:
                    progress(t, frames[-1], rgb)
                seq += 1
                time.sleep(max(0, 1 / policy.fps - (time.monotonic() - loop)))
        return CaptureResult(
            frames,
            policy.duration_s,
            {
                "camera_index": camera_index,
                "mediapipe_version": version("mediapipe"),
                "model_url": MODEL_URL,
                "model_sha256": sha256(model_path.read_bytes()).hexdigest(),
                "quality_signal": "binary usable landmark geometry; not a confidence probability",
                "hand": policy.hand,
                "observed_frames": len(frames),
                "effective_fps": round(len(frames) / policy.duration_s, 2),
            },
        )
    except CameraUnavailable:
        raise
    except Exception as exc:
        raise CameraUnavailable(
            f"Camera assessment failed ({type(exc).__name__}). "
            "Check the model and camera; the synthetic lab remains available."
        ) from exc
    finally:
        cap.release()
