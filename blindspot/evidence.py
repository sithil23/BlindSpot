"""Audit availability on an explicit clock, including the silent tail of a session."""

import math

from blindspot.models import Evidence, Observation, Protocol, usable

REASONS = {
    "no_valid_frames": "No usable hand measurements were recorded.",
    "low_coverage": "Too little of the assessment had usable tracking.",
    "long_gap": "A tracking gap exceeded the prototype quality setting.",
    "stale_stream": "The measurement stream stopped before the assessment ended.",
    "short_session": "The assessment ended before the required duration.",
    "invalid_data": "Malformed or out-of-order measurements were rejected.",
    "replayed_sequence": "Repeated or backwards frame sequence numbers were rejected.",
}


def evaluate_evidence(
    frames: list[Observation], policy: Protocol, duration_s: float, reasons: set[str]
) -> Evidence:
    reasons = set(reasons)
    expected = max(1, math.ceil(duration_s * policy.fps))
    valid = [f for f in frames if usable(f, policy)]
    bins = {int(f.t * policy.fps + 1e-7) for f in valid}
    coverage = min(1.0, len(bins) / expected)
    times = sorted({f.t for f in valid})
    period = 1 / policy.fps
    gaps = [times[0], max(0.0, duration_s - times[-1] - period)] if times else [duration_s]
    gaps += [max(0.0, b - a - period) for a, b in zip(times, times[1:], strict=False)]
    longest = max(gaps)
    age = max(0.0, duration_s - times[-1] - period) if times else None
    if not valid:
        reasons.add("no_valid_frames")
    if coverage < policy.min_coverage:
        reasons.add("low_coverage")
    if longest > policy.max_gap_s:
        reasons.add("long_gap")
    if age is None or age > policy.stale_s:
        reasons.add("stale_stream")
    if duration_s < policy.min_duration_s or duration_s < policy.duration_s - period:
        reasons.add("short_session")
    return Evidence(
        not reasons, coverage, len(bins), expected, longest, age, tuple(sorted(reasons))
    )
