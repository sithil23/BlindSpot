"""Synthetic dose-equivalent monitoring for mission demos; not dosimetry."""

from copy import deepcopy
from datetime import datetime, timezone
from math import cos, isfinite, sin

SCHEMA = 'blindspot.synthetic.radiation.v1'
_CREW = ('CREW-01', 'CREW-02', 'CREW-03')
_HABITATS = ('Habitat A', 'Habitat B')


def radiation_exposure(rate_samples, interval_seconds):
    if not isinstance(interval_seconds, (int, float)) or not isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError('Invalid sampling interval')
    if not rate_samples or any(v is None or not isinstance(v, (int, float)) or not isfinite(v) or v < 0 for v in rate_samples):
        return None
    return sum((a + b) / 2 for a, b in zip(rate_samples, rate_samples[1:])) * interval_seconds / 3600


def _reading(rate, elapsed, phase):
    wave_period = 80.0
    amp = 0.025 * rate
    current = rate + amp * sin(elapsed / wave_period + phase)
    total = (rate * elapsed + amp * wave_period * (cos(phase) - cos(elapsed / wave_period + phase))) / 3600
    return {
        'dose_equivalent_rate_uSv_h': round(current, 4),
        'cumulative_dose_uSv': round(max(total, 0), 5),
        'unit': 'uSv/h', 'cumulative_unit': 'uSv', 'quality': 'adequate',
        'observed_elapsed_s': elapsed,
    }


def build_radiation_payload(elapsed_seconds=0, seed=42):
    if type(elapsed_seconds) is not int or elapsed_seconds < 0 or type(seed) is not int:
        raise ValueError('Invalid radiation time or seed')
    return {
        'schema': SCHEMA, 'source': 'synthetic_radiation',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': elapsed_seconds,
        'radiation_quantity': 'dose_equivalent',
        'radiation_type': 'illustrative_mixed_field',
        'crews': {crew: _reading(10 + i * 2 + (seed % 3) * .25, elapsed_seconds, i * .8) for i, crew in enumerate(_CREW)},
        'habitats': {name: _reading(5 + i * 1.5, elapsed_seconds, i * .5) for i, name in enumerate(_HABITATS)},
    }


def validate_radiation_payload(payload, max_age_seconds=30):
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA or payload.get('source') != 'synthetic_radiation':
        raise ValueError('Unrecognized radiation source')
    try:
        when = datetime.fromisoformat(payload['generated_at'])
        if when.tzinfo is None:
            raise ValueError('Missing timezone')
        age = (datetime.now(timezone.utc) - when).total_seconds()
        if not -10 <= age <= max_age_seconds:
            raise ValueError('Stale radiation response')
        seconds = payload['elapsed_seconds']
        if type(seconds) is not int or seconds < 0:
            raise ValueError('Invalid elapsed time')
        if payload['radiation_quantity'] != 'dose_equivalent' or payload['radiation_type'] != 'illustrative_mixed_field':
            raise ValueError('Unexpected radiation measurement type')
        if set(payload['crews']) != set(_CREW) or set(payload['habitats']) != set(_HABITATS):
            raise ValueError('Incomplete sensor layout')
        for group in ('crews', 'habitats'):
            for row in payload[group].values():
                if not isinstance(row, dict) or row.get('unit') != 'uSv/h' or row.get('cumulative_unit') != 'uSv':
                    raise ValueError('Incorrect radiation units')
                if row.get('quality') not in ('adequate', 'insufficient'):
                    raise ValueError('Invalid quality')
                rate, total = row.get('dose_equivalent_rate_uSv_h'), row.get('cumulative_dose_uSv')
                if row['quality'] == 'adequate':
                    if any(type(v) not in (int, float) or not isfinite(v) or v < 0 for v in (rate, total)):
                        raise ValueError('Invalid radiation reading')
                    if row.get('observed_elapsed_s') != seconds:
                        raise ValueError('Stale radiation measurement')
                elif rate is not None or total is not None:
                    raise ValueError('Insufficient radiation data cannot carry a dose')
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError(f'Invalid radiation response: {exc}') from exc
    return payload


def apply_radiation_demo(payload, scenario, crew):
    if scenario not in ('routine', 'radiation_event', 'radiation_sensor_loss'):
        raise ValueError('Invalid radiation scenario')
    if crew not in _CREW:
        raise ValueError('Invalid crew')
    if payload is None:
        return None, []
    result = deepcopy(payload)
    if scenario == 'routine':
        return result, []
    item = result['crews'][crew]
    if item['quality'] != 'adequate':
        return result, [{'kind': 'evidence', 'message': f'DEMO · {crew} radiation feed unavailable; no value injected.'}]
    if scenario == 'radiation_event':
        item['dose_equivalent_rate_uSv_h'] = round(item['dose_equivalent_rate_uSv_h'] * 3.5, 4)
        return result, [{'kind': 'warning', 'message': f'DEMO · {crew} radiation dose-rate spike. Review simulated exposure. Cumulative dose unchanged by this instantaneous demonstration.'}]
    item.update(quality='insufficient', dose_equivalent_rate_uSv_h=None, cumulative_dose_uSv=None, observed_elapsed_s=None)
    return result, [{'kind': 'evidence', 'message': f'DEMO · {crew} radiation dosimeter disconnected. Exposure total unavailable.'}]


def radiation_flags(payload, crew_ids=None, habitat_ids=None):
    if payload is None:
        return [{'kind': 'feed', 'message': 'Radiation feed unavailable. Exposure cannot be assessed.'}]
    flags = []
    for group, names in (('crews', crew_ids), ('habitats', habitat_ids)):
        selected = names if names is not None else payload[group].keys()
        for name in selected:
            if payload[group][name]['quality'] != 'adequate':
                flags.append({'kind': 'evidence', 'message': f'{name} radiation measurement unavailable; cumulative exposure unknown.'})
    return flags
