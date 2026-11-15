import math
import unittest

from blindspot.assessment import assess
from blindspot.models import Observation, Protocol
from blindspot.synthetic import make_demo
from blindspot.tapping import TapCounter


class TappingTests(unittest.TestCase):
    def test_complete_cycle_counts_once_despite_boundary_jitter(self):
        counter = TapCounter(Protocol())
        for t, value in enumerate([0.9, 0.6, 0.5, 0.2, 0.3, 0.4, 0.9]):
            counter.update(Observation(t * 0.1, value, 1.0, t))
        self.assertEqual(counter.count, 1)

    def test_tracking_loss_cannot_complete_a_cycle(self):
        counter = TapCounter(Protocol())
        for t, value in enumerate([0.9, 0.2, None, 0.9]):
            counter.update(Observation(t * 0.1, value, 1.0, t))
        self.assertEqual(counter.count, 0)

    def test_long_gap_resets_cycle(self):
        counter = TapCounter(Protocol())
        for t, value in [(0, 0.9), (0.1, 0.2), (2, 0.9)]:
            counter.update(Observation(t, value, 1.0, int(t * 100)))
        self.assertEqual(counter.count, 0)

    def test_repeated_values_are_not_sensor_failure(self):
        frames = [Observation(i / 15, 0.9, 1.0, i) for i in range(225)]
        result = assess(frames, Protocol(), 15)
        self.assertTrue(result.evidence.sufficient)
        self.assertEqual(result.count, 0)


class EvidenceTests(unittest.TestCase):
    def test_clean_demo_has_30_cycles(self):
        result = assess(make_demo(), Protocol(), 15)
        self.assertEqual(result.count, 30)
        self.assertTrue(result.evidence.sufficient)

    def test_dropout_changes_count_but_blocks_interpretation(self):
        result = assess(make_demo("tracking_loss"), Protocol(), 15)
        self.assertLess(result.count, 30)
        self.assertFalse(result.evidence.sufficient)
        self.assertIn("low_coverage", result.evidence.reasons)

    def test_stopped_stream_expires_without_a_new_frame(self):
        frames = make_demo()[:100]
        result = assess(frames, Protocol(), 15)
        self.assertIn("stale_stream", result.evidence.reasons)
        self.assertFalse(result.evidence.sufficient)

    def test_empty_is_missing_not_zero_performance(self):
        result = assess([], Protocol(), 15)
        self.assertIsNone(result.rate_hz)
        self.assertIn("no_valid_frames", result.evidence.reasons)

    def test_non_finite_and_out_of_order_input_is_rejected(self):
        frames = make_demo()
        frames[10] = Observation(frames[10].t, math.nan, 1, 10)
        frames[20] = Observation(-1, 0.9, 1, 20)
        result = assess(frames, Protocol(), 15)
        self.assertIn("invalid_data", result.evidence.reasons)
        self.assertFalse(result.evidence.sufficient)

    def test_replayed_sequence_is_detected_without_using_equal_values(self):
        result = assess(make_demo("replayed_frames"), Protocol(), 15)
        self.assertIn("replayed_sequence", result.evidence.reasons)

    def test_few_frames_cannot_become_a_valid_short_session(self):
        result = assess(make_demo()[:30], Protocol(), 2)
        self.assertIn("short_session", result.evidence.reasons)

    def test_policy_is_validated(self):
        with self.assertRaises(ValueError):
            Protocol(fps=0)
        with self.assertRaises(ValueError):
            Protocol(close_ratio=0.9, open_ratio=0.2)


def test_cycle_does_not_bridge_a_missing_packet_sequence():
    frames = [
        Observation(0, 0.9, 1, 0),
        Observation(0.07, 0.15, 1, 1),
        Observation(0.14, 0.9, 1, 3),
    ]
    assert assess(frames, Protocol(), 15).count == 0
