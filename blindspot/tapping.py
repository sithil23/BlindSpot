"""Hysteresis counter: open -> closed -> open, never across missing evidence."""

from blindspot.models import Observation, Protocol, usable


class TapCounter:
    def __init__(self, policy: Protocol):
        self.policy = policy
        self.state = "unknown"
        self.started = 0.0
        self.last_t: float | None = None
        self.last_tap = -float("inf")
        self.tap_times: list[float] = []

    @property
    def count(self) -> int:
        return len(self.tap_times)

    def reset(self):
        self.state = "unknown"

    def update(self, frame: Observation):
        if self.last_t is not None and (
            frame.t <= self.last_t or frame.t - self.last_t > self.policy.bridge_gap_s
        ):
            self.reset()
        self.last_t = frame.t
        if not usable(frame, self.policy):
            self.reset()
            return
        distance = frame.distance
        assert distance is not None
        if distance >= self.policy.open_ratio:
            if (
                self.state == "closed"
                and frame.t - self.started >= self.policy.min_cycle_s
                and frame.t - self.last_tap >= self.policy.min_cycle_s
            ):
                self.tap_times.append(frame.t)
                self.last_tap = frame.t
            self.state = "open"
            self.started = frame.t
        elif distance <= self.policy.close_ratio and self.state == "open":
            self.state = "closed"
