



from __future__ import annotations

import copy
import json
import math
import random
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Metric:
    label: str
    unit: str
    baseline: float
    jitter: float
    noteworthy_difference: float  # visual demo sensitivity, not a health threshold
    group: str


METRICS: dict[str, Metric] = {
    'ecg_hr': Metric('ECG-derived heart rate', 'bpm', 73, 0.8, 10, 'ECG'),
    'ecg_rmssd': Metric('ECG-derived RMSSD', 'ms', 44, 1.2, 12, 'ECG'),
    'emg_rms': Metric('EMG RMS amplitude', 'mV', 0.38, 0.012, 0.13, 'EMG'),
    'emg_activation': Metric('EMG task activation', '%', 74, 1.2, 12, 'EMG'),
    'spo2': Metric('Pulse oximeter SpO₂', '%', 98.0, 0.12, 1.4, 'Pulse oximeter'),
    'pulse_rate': Metric('Optical pulse rate', 'bpm', 73, 0.8, 10, 'Pulse oximeter'),
    'gaze_latency': Metric('Gaze target latency', 'ms', 240, 5, 65, 'Eye movement'),
    'gaze_error': Metric('Gaze target error', 'degrees', 2.4, 0.09, 1.2, 'Eye movement'),
    'finger_taps': Metric('Finger taps per 15 s', 'cycles', 30, 0.6, 5, 'Motor task'),
    'cabin_co2': Metric('Cabin CO₂', 'ppm', 650, 8, 400, 'Habitat'),
    'cabin_o2': Metric('Cabin O₂', '%', 20.9, 0.02, 0.8, 'Habitat'),
}
SCENARIOS = {
    'nominal': 'Routine pre/post assessment',
    'exertion': 'Post-EVA exertion-like changes',
    'sensor_loss': 'Pulse-ox data missing',
    'replay': 'ECG feed timestamp/sequence replay',
    'mixed': 'Exertion-like changes with missing sensor',
}
# Example inputs to illustrate changes; not clinical, mission, or causal models.
POST_SHIFTS = {
    'ecg_hr': 18.0, 'ecg_rmssd': -14.0, 'emg_rms': 0.21,
    'emg_activation': -17.0, 'pulse_rate': 18.0,
    'gaze_latency': 85.0, 'gaze_error': 1.7, 'finger_taps': -7.0,
    'cabin_co2': 490.0,
}
MAX_BYTES = 512_000
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')


def build_assessment(participant: str, eva_id: str, phase: str,
                     scenario: str = 'nominal', seed: int = 42) -> dict[str, Any]:
    """An independent program can run this to create a transferable export."""
    if not all(isinstance(x, str) and NAME.fullmatch(x) for x in (participant, eva_id)):
        raise ValueError('Use short alphanumeric crew and EVA codes')
    if phase not in {'pre', 'post'} or scenario not in SCENARIOS:
        raise ValueError('Invalid phase or simulation scenario')
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 2**31 - 1:
        raise ValueError('Invalid seed')
    rng = random.Random(f'{participant}/{eva_id}/{seed}')
    values: dict[str, Any] = {}
    for key, spec in METRICS.items():
        # Identical seed means the same crew's two snapshots have comparable noise.
        value = spec.baseline + rng.gauss(0, spec.jitter)
        if phase == 'post' and scenario in {'exertion', 'mixed'}:
            value += POST_SHIFTS.get(key, 0)
        if key == 'finger_taps':
            value = float(round(value))
        value = round(value, 3)
        quality = 'ok'
        observed_at = 60
        seq = 60
        if phase == 'post' and scenario in {'sensor_loss', 'mixed'} and key == 'spo2':
            value, quality, observed_at = None, 'missing', None
        if phase == 'post' and scenario == 'replay' and key in {'ecg_hr', 'ecg_rmssd'}:
            quality, observed_at, seq = 'replayed', 12, 12
        values[key] = {
            'value': value, 'unit': spec.unit, 'source': 'synthetic',
            'quality': quality, 'observed_at_s': observed_at, 'sequence': seq,
        }
    return {
        'schema_version': 1, 'origin': 'synthetic_simulator',
        'participant': participant, 'eva_id': eva_id, 'phase': phase,
        'scenario': scenario, 'seed': seed, 'export_time_s': 60,
        'measurements': values,
        'disclaimer': 'Synthetic only; no real sensor or camera measurements; not medical or flight-qualified.',
    }


def decode_assessment(blob: bytes) -> dict[str, Any]:
    """Strictly validate imported, untrusted simulation exports before comparison."""
    if not isinstance(blob, bytes) or len(blob) > MAX_BYTES:
        raise ValueError('Export exceeds 512 KB or is invalid')
    try:
        data = json.loads(blob.decode('utf-8'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError('Invalid JSON sensor export') from exc
    if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('origin') != 'synthetic_simulator':
        raise ValueError('Unsupported or non-synthetic sensor export')
    if any(not isinstance(data.get(k), str) or not NAME.fullmatch(data[k]) for k in ('participant', 'eva_id')):
        raise ValueError('Invalid crew or EVA identifier')
    if data.get('phase') not in ('pre', 'post') or data.get('scenario') not in SCENARIOS:
        raise ValueError('Invalid phase or scenario')
    readings = data.get('measurements')
    if not isinstance(readings, dict) or set(readings) != set(METRICS):
        raise ValueError('Missing or unknown measurement channels')
    t = data.get('export_time_s')
    if type(t) is not int or not 0 <= t <= 100_000_000:
        raise ValueError('Invalid capture time')
    for key, spec in METRICS.items():
        r = readings[key]
        if not isinstance(r, dict) or r.get('unit') != spec.unit:
            raise ValueError(f'Invalid metadata for {key}')
        if r.get('source') != 'synthetic':
            if not (key == 'finger_taps' and data['phase'] == 'pre'
                    and r.get('source') == 'webcam'
                    and isinstance(data.get('camera_checks'), dict)
                    and isinstance(data['camera_checks'].get('tap'), dict)
                    and r.get('value') == data['camera_checks']['tap'].get('count')
                    and data['camera_checks']['tap'].get('quality') == ('adequate' if r.get('quality') == 'ok' else 'insufficient_evidence')):
                raise ValueError(f'Invalid sensor provenance for {key}')
        if r.get('quality') not in ('ok', 'missing', 'stale', 'replayed'):
            raise ValueError(f'Invalid quality flag for {key}')
        value = r.get('value')
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError(f'Invalid numeric value for {key}')
        if value is None and r['quality'] == 'ok':
            raise ValueError(f'Unflagged missing sample for {key}')
        observed = r.get('observed_at_s')
        seq = r.get('sequence')
        if observed is not None and (type(observed) is not int or not 0 <= observed <= t):
            raise ValueError(f'Invalid sample timestamp for {key}')
        if seq is not None and (type(seq) is not int or not 0 <= seq <= 100_000_000):
            raise ValueError(f'Invalid sequence for {key}')
    checks = data.get('camera_checks')
    if checks is not None:
        if data['phase'] != 'pre' or not isinstance(checks, dict) or set(checks) - {'tap', 'eye'}:
            raise ValueError('Invalid camera assessment placement')
        for name, c in checks.items():
            if not isinstance(c, dict) or c.get('source') != 'local_webcam' or c.get('quality') not in ('adequate', 'insufficient_evidence'):
                raise ValueError('Invalid camera evidence metadata')
            numeric = ('count', 'coverage', 'duration_s') if name == 'tap' else ('horizontal_range', 'coverage', 'duration_s', 'samples')
            for k in numeric:
                v = c.get(k)
                if v is not None and (type(v) not in (int, float) or not math.isfinite(v)):
                    raise ValueError('Nonfinite camera measurement')
            if not 0 <= c.get('coverage', -1) <= 1 or not 0 < c.get('duration_s', -1) <= 30:
                raise ValueError('Invalid camera coverage/duration')
            if name == 'eye':
                if c.get('method') != 'opencv_pupil_proxy_v1' or type(c.get('samples')) is not int or c['samples'] < 0:
                    raise ValueError('Invalid eye tracking method')
                v = c.get('horizontal_range')
                if v is not None and not 0 <= v <= 1:
                    raise ValueError('Invalid eye movement range')
                if c['quality'] == 'adequate' and v is None:
                    raise ValueError('Adequate eye tracking requires a measured range')
            else:
                if not isinstance(c.get('protocol_id'), str) or len(c['protocol_id']) > 128 or c['protocol_id'] == '':
                    raise ValueError('Invalid tapping protocol')
                if c.get('count') is not None and (type(c['count']) is not int or c['count'] < 0 or c['count'] > 1000):
                    raise ValueError('Invalid tap count')
                if c['quality'] == 'adequate' and c.get('count') is None:
                    raise ValueError('Missing adequate tap count')
        if 'tap' in checks and readings['finger_taps']['source'] != 'webcam':
            raise ValueError('Tap check is not attached')
    return data


def attach_pre_eva_camera(pre: dict, taps: dict | None = None, eye: dict | None = None) -> dict:
    """Bind direct local webcam checks to a synthetic reference without fabricating other channels."""
    pre = decode_assessment(json.dumps(pre, allow_nan=False).encode())
    if pre['phase'] != 'pre':
        raise ValueError('Camera reference must be pre-EVA')
    out = copy.deepcopy(pre)
    checks = out.setdefault('camera_checks', {})
    if taps is not None:
        sufficient = taps.get('sufficient') is True
        count = taps.get('count')
        duration = taps.get('duration_s')
        coverage = taps.get('coverage')
        protocol = taps.get('protocol_id')
        if (type(count) is not int or count < 0 or count > 1000 or
            type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0 or duration > 30 or
            type(coverage) not in (int, float) or not math.isfinite(coverage) or not 0 <= coverage <= 1 or
            not isinstance(protocol, str) or not protocol or len(protocol) > 128):
            raise ValueError('Invalid hand capture metadata')
        quality = 'adequate' if sufficient else 'insufficient_evidence'
        checks['tap'] = {'source': 'local_webcam', 'quality': quality,
                         'count': count if sufficient else None,
                         'coverage': coverage, 'duration_s': duration, 'protocol_id': protocol}
        channel = out['measurements']['finger_taps']
        channel['source'] = 'webcam'
        channel['value'] = count if sufficient else None
        channel['quality'] = 'ok' if sufficient else 'missing'
    if eye is not None:
        quality = eye.get('quality')
        if quality not in ('adequate', 'insufficient_evidence') or eye.get('method') != 'opencv_pupil_proxy_v1':
            raise ValueError('Invalid eye capture method/quality')
        checks['eye'] = {'source': 'local_webcam', 'quality': quality,
                         'horizontal_range': eye.get('horizontal_range') if quality == 'adequate' else None,
                         'coverage': eye.get('coverage'), 'samples': eye.get('samples'),
                         'duration_s': eye.get('duration_s'), 'method': eye.get('method')}
    return decode_assessment(json.dumps(out, allow_nan=False).encode())


def compare_camera_checks(pre: dict, post: dict) -> dict:
    """Never directly compare camera-derived eye proxy against synthetic degrees/latency."""
    checks = pre.get('camera_checks', {})
    report = {}
    if 'eye' in checks:
        eye = checks['eye']
        report['eye'] = {'status': 'pre_only' if eye['quality'] == 'adequate' else 'insufficient_evidence',
                         'pre': eye.get('horizontal_range'), 'post': None,
                         'note': 'Post-EVA synthetic gaze angle/latency is not comparable to the pre-EVA camera pupil-position proxy.'}
    if 'tap' in checks:
        report['tap'] = {'status': 'different_measurement_sources',
                         'pre': checks['tap'].get('count'),
                         'post': post['measurements']['finger_taps'].get('value'),
                         'note': 'Webcam observation and simulated tap count are from different sources; this is not a measured performance change.'}
    return report


def compare_assessments(pre: dict, post: dict) -> dict:

    pre = decode_assessment(json.dumps(pre, allow_nan=False).encode())
    post = decode_assessment(json.dumps(post, allow_nan=False).encode())
    if pre['phase'] != 'pre' or post['phase'] != 'post':
        raise ValueError('Comparison requires PRE then POST')
    if (pre['participant'], pre['eva_id']) != (post['participant'], post['eva_id']):
        raise ValueError('Crew/EVA identity mismatch: comparison refused')
    result = {}
    inadequate = 0
    changed = 0
    for key, spec in METRICS.items():
        a, b = pre['measurements'][key], post['measurements'][key]
        reasons = []
        for phase, entry, bundle in (('pre', a, pre), ('post', b, post)):
            if entry['value'] is None:
                reasons.append(f'{phase}: missing')
            if entry['quality'] != 'ok':
                reasons.append(f"{phase}: flagged {entry['quality']}")
            stamp = entry['observed_at_s']
            if stamp is None or bundle['export_time_s'] - stamp > 5:
                reasons.append(f'{phase}: timestamp missing or stale')
            if entry['sequence'] is None or entry['sequence'] < bundle['export_time_s'] - 5:
                reasons.append(f'{phase}: sequence outdated')
        if a.get('source') != b.get('source'):
            inadequate += 1
            result[key] = {'label': spec.label, 'unit': spec.unit,
                           'pre': a['value'] if a['quality'] == 'ok' else None,
                           'post': b['value'] if b['quality'] == 'ok' else None,
                           'delta': None, 'status': 'different_measurement_sources',
                           'reasons': ['webcam versus synthetic readings are not like-for-like']}
            continue
        if reasons:
            inadequate += 1
            result[key] = {'label': spec.label, 'unit': spec.unit, 'pre': a['value'] if not any(x.startswith('pre:') for x in reasons) else None,
                           'post': None, 'delta': None, 'status': 'insufficient_evidence', 'reasons': reasons}
            continue
        delta = round(b['value'] - a['value'], 3)
        status = 'change_observed' if abs(delta) >= spec.noteworthy_difference else 'similar_observation'
        changed += status == 'change_observed'
        result[key] = {'label': spec.label, 'unit': spec.unit, 'pre': a['value'], 'post': b['value'],
                       'delta': delta, 'status': status, 'reasons': []}
    overall = ('insufficient_evidence' if inadequate else
               'changes_observed' if changed else 'no_large_descriptive_change')
    return {'camera_checks': compare_camera_checks(pre, post), 'schema_version': 1, 'participant': pre['participant'], 'eva_id': pre['eva_id'],
            'overall': overall, 'metrics': result, 'missing_or_unreliable_channels': inadequate,
            'changed_channels': changed, 'origin': 'synthetic_simulator',
            'method': 'Fixed illustrative absolute-difference cutoffs; not validated clinical thresholds.',
            'interpretation': ('Some readings are missing or unreliable; a complete health comparison is not possible.' if inadequate else
                               'Some sensor-derived observations changed. Cause and medical significance cannot be inferred.' if changed else
                               'No large difference under illustrative cutoffs. This does not establish good health or EVA readiness.'),
            'not_for_medical_or_flight_use': True}
