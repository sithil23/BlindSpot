import json
import pytest

from blindspot.eva import METRICS, build_assessment, compare_assessments, decode_assessment


def test_deterministic_pre_and_post_scenarios():
    a = build_assessment('CREW-01', 'EVA-07', 'pre', scenario='nominal', seed=4)
    b = build_assessment('CREW-01', 'EVA-07', 'pre', scenario='nominal', seed=4)
    assert a == b
    assert set(a['measurements']) == set(METRICS)
    assert a['origin'] == 'synthetic_simulator'
    post = build_assessment('CREW-01', 'EVA-07', 'post', scenario='exertion', seed=4)
    comparison = compare_assessments(a, post)
    assert comparison['overall'] == 'changes_observed'
    assert comparison['metrics']['ecg_hr']['status'] == 'change_observed'
    assert comparison['metrics']['emg_rms']['status'] == 'change_observed'


def test_missing_and_stale_abstain_not_normal():
    before = build_assessment('A', 'EVA1', 'pre')
    after = build_assessment('A', 'EVA1', 'post', scenario='sensor_loss')
    report = compare_assessments(before, after)
    assert report['metrics']['spo2']['status'] == 'insufficient_evidence'
    assert report['metrics']['spo2']['post'] is None
    assert report['overall'] == 'insufficient_evidence'


def test_stale_and_replay_rejected():
    before = build_assessment('A', 'EVA1', 'pre')
    after = build_assessment('A', 'EVA1', 'post', scenario='replay')
    report = compare_assessments(before, after)
    assert report['overall'] == 'insufficient_evidence'
    assert report['metrics']['ecg_hr']['status'] == 'insufficient_evidence'


def test_mismatched_identity_phase_and_protocol_rejected():
    before = build_assessment('A', 'EVA1', 'pre')
    with pytest.raises(ValueError):
        compare_assessments(before, build_assessment('B', 'EVA1', 'post'))
    with pytest.raises(ValueError):
        compare_assessments(before, build_assessment('A', 'EVA2', 'post'))
    with pytest.raises(ValueError):
        compare_assessments(before, before)
    after = build_assessment('A', 'EVA1', 'post')
    after['measurements']['spo2']['unit'] = 'bpm'
    with pytest.raises(ValueError):
        decode_assessment(json.dumps(after).encode())


def test_untrusted_payload_rejects_unsafe_values():
    before = build_assessment('A', 'EVA1', 'pre')
    before['measurements']['spo2']['value'] = float('nan')
    with pytest.raises(ValueError):
        decode_assessment(json.dumps(before).encode())
    with pytest.raises(ValueError):
        decode_assessment(b'{' + b'x' * 600_000 + b'}')
    with pytest.raises(ValueError):
        decode_assessment(b'not json')


def test_camera_metric_not_fabricated_as_measured():
    before = build_assessment('A', 'EVA1', 'pre')
    assert before['measurements']['gaze_latency']['source'] == 'synthetic'
    assert before['measurements']['finger_taps']['source'] == 'synthetic'


def test_normal_noise_not_false_health_diagnosis():
    before = build_assessment('A', 'EVA1', 'pre')
    after = build_assessment('A', 'EVA1', 'post', scenario='nominal')
    report = compare_assessments(before, after)
    assert report['overall'] == 'no_large_descriptive_change'
    assert report['not_for_medical_or_flight_use'] is True
    assert 'diagnosis' not in report
