"""Preserve missing input and reject malformed or replayed observations."""

import math

from blindspot.models import Observation


def validate_frames(frames: list[Observation], duration_s: float):
    accepted: list[Observation] = []
    reasons: set[str] = set()
    last_t, last_seq = -1.0, -1
    for frame in frames:
        valid = True
        if (
            not math.isfinite(frame.t)
            or frame.t < 0
            or frame.t >= duration_s
            or frame.t <= last_t
            or not isinstance(frame.seq, int)
            or frame.seq < 0
            or not math.isfinite(frame.confidence)
            or not 0 <= frame.confidence <= 1
            or (
                frame.distance is not None
                and (not math.isfinite(frame.distance) or not 0 <= frame.distance <= 10)
            )
        ):
            reasons.add("invalid_data")
            valid = False
        if frame.seq <= last_seq:
            reasons.add("replayed_sequence")
            valid = False
        if valid:
            if last_seq >= 0 and frame.seq > last_seq + 1:
                accepted.append(Observation(last_t, None, 0.0, last_seq))
            accepted.append(frame)
            last_t, last_seq = frame.t, frame.seq
        elif accepted:
            # Explicit invalid marker prevents the counter bridging a rejected frame.
            accepted.append(Observation(last_t, None, 0.0, last_seq))
    return accepted, reasons
