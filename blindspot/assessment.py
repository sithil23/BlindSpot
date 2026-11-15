"""Compose validation, counting and evidence without hiding measurement failures."""

import math

from blindspot.evidence import evaluate_evidence
from blindspot.models import Assessment, Observation, Protocol
from blindspot.tapping import TapCounter
from blindspot.validation import validate_frames


def assess(frames: list[Observation], policy: Protocol, duration_s: float) -> Assessment:
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be finite and positive")
    accepted, reasons = validate_frames(frames, duration_s)
    counter = TapCounter(policy)
    for frame in accepted:
        counter.update(frame)
    evidence = evaluate_evidence(accepted, policy, duration_s, reasons)
    return Assessment(
        counter.count,
        counter.count / duration_s if evidence.valid_frames else None,
        duration_s,
        evidence,
        tuple(counter.tap_times),
        policy.fingerprint,
    )
