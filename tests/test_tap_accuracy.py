"""Regressions for webcam taps whose landmark distances do not reach old thresholds."""

from blindspot.models import Observation, Protocol
from blindspot.tapping import TapCounter


def test_default_thresholds_count_moderate_open_close_distances():
    # A full movement need not attain the old 0.25/0.65 extreme distances.
    counter = TapCounter(Protocol())
    samples = [0.58, 0.48, 0.32, 0.43, 0.59, 0.48, 0.31, 0.46, 0.60]
    for i, d in enumerate(samples):
        counter.update(Observation(i * 0.075, d, 1.0, i))
    assert counter.count == 2


def test_distance_jitter_without_a_complete_close_open_cannot_count():
    counter = TapCounter(Protocol())
    for i, d in enumerate([0.6, 0.49, 0.46, 0.51, 0.47, 0.56, 0.48, 0.6]):
        counter.update(Observation(i * 0.08, d, 1.0, i))
    assert counter.count == 0


def test_tracking_loss_still_prevents_assembling_a_tap():
    counter = TapCounter(Protocol())
    for i, d in enumerate([0.6, 0.32, None, 0.6]):
        counter.update(Observation(i * 0.08, d, 1.0 if d is not None else 0.0, i))
    assert counter.count == 0
