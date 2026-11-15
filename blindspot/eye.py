




from __future__ import annotations

import math
import time
from collections.abc import Callable
from statistics import quantiles
from typing import Any

METHOD = 'opencv_pupil_proxy_v1'


class EyeCameraUnavailable(RuntimeError):
    pass


def analyze_eye_samples(samples: list[tuple[float, float]], total_frames: int, duration_s: float) -> dict[str, Any]:
    """Summarize normalized pupil horizontal displacement (-0.5 to +0.5)."""
    if total_frames < 0 or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError('Invalid eye capture duration/frame count')
    clean = [(x, t) for x, t in samples
             if math.isfinite(x) and math.isfinite(t) and -0.5 <= x <= 0.5 and 0 <= t <= duration_s]
    coverage = round(min(1.0, len(clean) / total_frames), 4) if total_frames else 0.0
    positions = sorted(x for x, _ in clean)
    # Avoid outlier spikes by using a central 10%-90% movement span.
    if len(positions) >= 10:
        q = quantiles(positions, n=10, method='inclusive')
        movement = max(0.0, q[8] - q[0])
    elif len(positions) >= 2:
        movement = positions[-1] - positions[0]
    else:
        movement = None
    adequate = len(clean) >= 20 and duration_s >= 5 and coverage >= 0.70
    return {
        'method': METHOD,
        'quality': 'adequate' if adequate else 'insufficient_evidence',
        'horizontal_range': round(movement, 4) if adequate and movement is not None else None,
        'coverage': coverage,
        'samples': len(clean),
        'duration_s': round(duration_s, 3),
        'source': 'local_webcam',
        'explanation': ('Exploratory pupil-position movement proxy, not gaze angle, latency, '
                        'visual acuity, vestibular function or medical diagnosis.'),
    }


def pupil_horizontal_offset(eye_gray) -> float | None:
    """Heuristic pupil location within eye ROI. Reject tiny/flat/invalid images."""
    import cv2
    import numpy as np

    if eye_gray is None or eye_gray.ndim != 2 or min(eye_gray.shape) < 12:
        return None
    h, w = eye_gray.shape

    y0, y1 = int(h * 0.30), int(h * 0.75)
    x0, x1 = int(w * 0.12), int(w * 0.88)
    region = eye_gray[y0:y1, x0:x1]
    if region.size < 64 or float(region.std()) < 8:
        return None
    blurred = cv2.GaussianBlur(region, (5, 5), 0)
    # Use darkest 15% to reject isolated dark eyelashes.
    threshold = float(np.percentile(blurred, 15))
    mask = blurred <= threshold
    if mask.sum() < 4 or mask.sum() > region.size * 0.42:
        return None
    ys, xs = np.where(mask)
    center = x0 + float(xs.mean())
    offset = center / w - 0.5
    return round(offset, 4) if math.isfinite(offset) and abs(offset) <= 0.5 else None


def capture_eye_motion(duration_s: float = 8.0, camera_index: int = 0,
                       progress: Callable[[float, bool], None] | None = None) -> dict[str, Any]:





    if duration_s < 5 or duration_s > 30:
        raise ValueError('Eye capture duration must be 5-30 seconds')
    try:
        import cv2
    except (ImportError, OSError) as exc:
        raise EyeCameraUnavailable('OpenCV unavailable. Install camera dependencies.') from exc
    face_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    eye_path = cv2.data.haarcascades + 'haarcascade_eye.xml'
    face_detector = cv2.CascadeClassifier(face_path)
    eye_detector = cv2.CascadeClassifier(eye_path)
    if face_detector.empty() or eye_detector.empty():
        raise EyeCameraUnavailable('OpenCV Haar classifiers were not found.')
    cam = cv2.VideoCapture(camera_index)
    total = 0
    readings: list[tuple[float, float]] = []
    try:
        if not cam.isOpened():
            raise EyeCameraUnavailable('Cannot open webcam; close other camera applications.')
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        start = time.monotonic()
        while time.monotonic() - start < duration_s:
            ok, frame = cam.read()
            elapsed = min(duration_s, time.monotonic() - start)
            total += 1
            measured = False
            if ok and frame is not None:
                if frame.shape[1] > 640:
                    frame = cv2.resize(frame, (640, round(frame.shape[0] * 640 / frame.shape[1])))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_detector.detectMultiScale(gray, 1.15, 4, minSize=(90, 90))
                if len(faces) == 1:
                    x, y, w, h = map(int, faces[0])
                    # Upper face only: reject mouth/nose false positives.
                    upper = gray[y:y + int(h * .55), x:x + w]
                    eyes = eye_detector.detectMultiScale(upper, 1.1, 5, minSize=(18, 12))
                    candidates = sorted(eyes, key=lambda e: e[2] * e[3], reverse=True)
                    if candidates:
                        ex, ey, ew, eh = map(int, candidates[0])
                        value = pupil_horizontal_offset(upper[ey:ey + eh, ex:ex + ew])
                        if value is not None:
                            readings.append((value, elapsed))
                            measured = True
            if progress and total % 8 == 0:
                progress(elapsed, measured)
        return analyze_eye_samples(readings, total, duration_s)
    except EyeCameraUnavailable:
        raise
    except Exception as exc:
        raise EyeCameraUnavailable(f'Eye assessment failed ({type(exc).__name__}); try better lighting.') from exc
    finally:
        cam.release()
