import copy
import json
import pytest

from blindspot.eva import (build_assessment, compare_assessments, decode_assessment,
                           attach_pre_eva_camera, compare_camera_checks)
from blindspot.eye import analyze_eye_samples


def test_eye_motion_range_and_missing_samples():
    series = [(-0.24, 0.1), (0.25, 0.2), (-0.18, 0.3), (0.2, 0.4)]
    result = analyze_eye_samples(series, total_frames=5, duration_s=2.0)
    assert result['horizontal_range'] is None
    assert result['coverage'] == 0.8
    assert result['quality'] == 'insufficient_evidence'  # too few samples/short task
    assert analyze_eye_samples([], 40, 8)['quality'] == 'insufficient_evidence'


def test_attach_valid_camera_taps_is_recorded_and_compared_with_provenance():
    pre = build_assessment('C1', 'E1', 'pre')
    tapped = attach_pre_eva_camera(pre, taps={'count': 29, 'duration_s': 15,
         'coverage': .95, 'sufficient': True, 'protocol_id': 'finger-v2'})
    loaded = decode_assessment(json.dumps(tapped).encode())
    assert loaded['measurements']['finger_taps']['source'] == 'webcam'
    assert loaded['measurements']['finger_taps']['value'] == 29
    report = compare_assessments(loaded, build_assessment('C1', 'E1', 'post'))
    assert report['metrics']['finger_taps']['status'] == 'different_measurement_sources'
    assert report['overall'] == 'insufficient_evidence'


def test_unreliable_taps_cannot_become_valid_reference():
    pre = build_assessment('C1', 'E1', 'pre')
    out = attach_pre_eva_camera(pre, taps={'count': 12, 'duration_s': 15,
         'coverage': .3, 'sufficient': False, 'protocol_id': 'finger-v2'})
    assert out['measurements']['finger_taps']['value'] is None
    assert out['measurements']['finger_taps']['quality'] == 'missing'


def test_reject_forged_webcam_source_on_other_channels_and_tampering():
    pre = build_assessment('C1', 'E1', 'pre')
    pre['measurements']['spo2']['source'] = 'webcam'
    with pytest.raises(ValueError):
        decode_assessment(json.dumps(pre).encode())
    pre = build_assessment('C1', 'E1', 'pre')
    pre['measurements']['finger_taps']['source'] = 'webcam'
    with pytest.raises(ValueError):
        decode_assessment(json.dumps(pre).encode())


def test_eye_capture_provenance_and_cross_source_comparison():
    pre = build_assessment('C1', 'E1', 'pre')
    eye = {'horizontal_range': .33, 'coverage': .92, 'samples': 45,
           'quality': 'adequate', 'duration_s': 8., 'method': 'opencv_pupil_proxy_v1'}
    attached = attach_pre_eva_camera(pre, eye=eye)
    parsed = decode_assessment(json.dumps(attached).encode())
    out = compare_assessments(parsed, build_assessment('C1', 'E1', 'post'))
    assert out['camera_checks']['eye']['status'] == 'pre_only'
    assert 'not comparable' in out['camera_checks']['eye']['note'].lower()


def test_unknown_extra_camera_payload_rejected():
    pre = build_assessment('C1', 'E1', 'pre')
    pre['camera_checks'] = {'eye': {'quality':'adequate', 'horizontal_range': float('nan')}}
    with pytest.raises(ValueError):
        decode_assessment(json.dumps(pre).encode())
