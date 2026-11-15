"""Deterministic motion and explicit transport/tracking faults, never medical data."""

from dataclasses import replace

from blindspot.models import Observation, Protocol

SCENARIOS = {
    "clean": "Clean tracking",
    "tracking_loss": "Hand hidden for 5 seconds",
    "stale_stream": "Stream stops after 6 seconds",
    "low_confidence": "Unusable detections for 5 seconds",
    "replayed_frames": "Frame sequence replay for 5 seconds",
}


def make_demo(scenario: str = "clean", policy: Protocol | None = None) -> list[Observation]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    policy = policy or Protocol()
    frames = []

    for i in range(round(policy.duration_s * policy.fps)):
        t = i / policy.fps
        phase = (t * 2) % 1
        distance = 0.9 if phase < 0.3 or phase >= 0.75 else 0.15
        frame = Observation(t, distance, 1.0, i)
        if 5 <= t < 10:
            if scenario == "tracking_loss":
                frame = replace(frame, distance=None, confidence=0)
            elif scenario == "low_confidence":
                frame = replace(frame, confidence=0.1)
            elif scenario == "replayed_frames":
                frame = replace(frame, seq=74)
        if scenario == "stale_stream" and t >= 6:
            break
        frames.append(frame)
    return frames
