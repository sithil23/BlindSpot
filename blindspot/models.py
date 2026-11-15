

import json
import math
from dataclasses import asdict, dataclass
from hashlib import sha256


@dataclass(frozen=True)
class Protocol:
    duration_s: float = 15.0
    fps: float = 15.0
    close_ratio: float = 0.34
    open_ratio: float = 0.56
    min_cycle_s: float = 0.12
    bridge_gap_s: float = 0.25
    min_coverage: float = 0.8
    max_gap_s: float = 1.0
    stale_s: float = 1.0
    min_confidence: float = 0.5
    min_duration_s: float = 10.0
    minimum_baselines: int = 3
    baseline_max_age_days: float = 30.0
    hand: str = "Right"
    version: str = "tapping-v2"

    def __post_init__(self):
        values = asdict(self)
        for name, value in values.items():
            if isinstance(value, (int, float)) and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        if not 0 < self.close_ratio < self.open_ratio:
            raise ValueError("close_ratio must be below open_ratio")
        if self.min_coverage > 1 or self.min_confidence > 1:
            raise ValueError("coverage and confidence must be in (0, 1]")
        if self.duration_s < self.min_duration_s or self.hand not in ("Left", "Right"):
            raise ValueError("invalid duration or hand")
        if self.minimum_baselines < 3:
            raise ValueError("at least three baseline sessions are required")

    @property
    def fingerprint(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True).encode()
        return sha256(raw).hexdigest()[:16]


@dataclass(frozen=True)
class Observation:
    t: float
    distance: float | None
    confidence: float
    seq: int


def usable(frame: Observation, policy: Protocol) -> bool:
    return (
        frame.distance is not None
        and math.isfinite(frame.distance)
        and 0 <= frame.distance <= 10
        and math.isfinite(frame.confidence)
        and policy.min_confidence <= frame.confidence <= 1
    )


@dataclass(frozen=True)
class Evidence:
    sufficient: bool
    coverage: float
    valid_frames: int
    expected_frames: int
    longest_gap_s: float
    age_s: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Assessment:
    count: int
    rate_hz: float | None
    duration_s: float
    evidence: Evidence
    tap_times: tuple[float, ...]
    protocol_id: str
