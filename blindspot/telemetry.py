



from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from statistics import median


@dataclass(frozen=True)
class Channel:
    label: str
    unit: str
    domain: str
    baseline: float
    noise: float


CHANNELS = {
    'heart_rate': Channel('Heart rate', 'bpm', 'crew', 74.0, 0.65),
    'spo2': Channel('Blood oxygen (SpO₂)', '%', 'crew', 98.0, 0.12),
    'respiration': Channel('Breathing rate', 'breaths/min', 'crew', 15.0, 0.20),
    'body_temp': Channel('Body temperature', '°C', 'crew', 36.7, 0.035),
    'cabin_o2': Channel('Cabin oxygen', '%', 'cabin', 20.9, 0.012),
    'cabin_co2': Channel('Cabin CO₂', 'ppm', 'cabin', 650.0, 5.0),
    'cabin_pressure': Channel('Cabin pressure', 'kPa', 'cabin', 101.3, 0.04),
    'cabin_temp': Channel('Cabin temperature', '°C', 'cabin', 22.0, 0.04),
    'humidity': Channel('Relative humidity', '%', 'cabin', 44.0, 0.15),
}
SCENARIOS = {
    'routine': 'Routine mission',
    'exercise': 'Exercise period',
    'co2_rise': 'Cabin CO₂ rising',
    'hr_dropout': 'Heart-rate sensor disconnect',
    'hr_stale': 'Heart-rate feed freezes',
}
NASA_ECLSS = 'https://www.nasa.gov/reference/environmental-control-and-life-support-systems-eclss/'


@dataclass(frozen=True)
class Reading:
    second: int
    channel: str
    value: float | None
    unit: str
    source: str = 'synthetic'
    observed_at: int | None = None
    quality_flag: str = 'ok'


def generate_mission(scenario: str = 'routine', seed: int = 42, duration: int = 120) -> list[Reading]:




    if scenario not in SCENARIOS:
        raise ValueError('Unknown scenario')
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('Seed must be an integer')
    if isinstance(duration, bool) or not isinstance(duration, int) or not 10 <= duration <= 3600:
        raise ValueError('Duration must be 10–3600 seconds')
    rng = random.Random(seed)
    states = {name: channel.baseline for name, channel in CHANNELS.items()}
    result: list[Reading] = []
    for second in range(duration):
        fraction = second / max(duration - 1, 1)
        for name, channel in CHANNELS.items():
            desired = channel.baseline + math.sin(second / 18 + len(name)) * channel.noise * 1.2
            if scenario == 'exercise' and name == 'heart_rate':
                desired += 42 * min(1, fraction * 2.5)
            if scenario == 'exercise' and name == 'respiration':
                desired += 9 * min(1, fraction * 2.5)
            if scenario == 'co2_rise' and name == 'cabin_co2':
                desired += 1500 * fraction

            states[name] += (desired - states[name]) * 0.16 + rng.gauss(0, channel.noise * 0.14)
            value = round(states[name], 2)
            observed_at = second
            flag = 'ok'
            if name == 'heart_rate' and scenario == 'hr_dropout' and fraction >= 0.55:
                value, flag = None, 'missing'
                observed_at = None
            elif name == 'heart_rate' and scenario == 'hr_stale' and fraction >= 0.55:
                observed_at = int((duration - 1) * 0.55) - 1
                flag = 'stale'
            result.append(Reading(second, name, value, channel.unit, 'synthetic', observed_at, flag))
    return result


def summarize(rows: list[Reading], at_second: int | None = None) -> dict[str, dict]:
    """Evidence quality and descriptive trend, not a medical risk score."""
    if not rows:
        raise ValueError('Missing telemetry')
    end = max(r.second for r in rows) if at_second is None else at_second
    if end < 0 or end > max(r.second for r in rows):
        raise ValueError('Invalid assessment time')
    summary: dict[str, dict] = {}
    for name, channel in CHANNELS.items():
        series = [r for r in rows if r.channel == name and r.second <= end]
        current = series[-1] if series else None
        recent = [r for r in series if r.second >= end - 9]
        stale = current is None or current.observed_at is None or end - current.observed_at > 3
        missing = current is None or current.value is None or current.quality_flag == 'missing'
        malformed = bool(current and (current.unit != channel.unit or current.source != 'synthetic'))
        reasons = []
        if missing:
            reasons.append('missing')
        elif stale:
            reasons.append('stale')
        if malformed:
            reasons.append('invalid_metadata')
        if len(recent) < min(5, end + 1) or any(r.value is None for r in recent):
            if 'missing' not in reasons:
                reasons.append('missing')
        adequate = not reasons
        earlier = [r.value for r in series if r.value is not None and r.second <= end - 10]
        trend = 'unknown'
        if adequate and len(earlier) >= 3:
            previous = median(earlier[-min(10, len(earlier)):])
            change = current.value - previous
            # Illustrative visualization thresholds, not environmental or medical alarms.
            threshold = max(channel.noise * 3, channel.baseline * .015)
            trend = 'rising' if change > threshold else 'falling' if change < -threshold else 'stable'
        summary[name] = {
            'label': channel.label, 'unit': channel.unit, 'domain': channel.domain,
            'value': current.value if adequate else None,
            'quality': 'adequate' if adequate else 'insufficient',
            'trend': trend, 'reasons': reasons,
            'explanation': ('Illustrative simulated reading; descriptive trend only.'
                            if adequate else 'Reading missing or stale. Verify this sensor; do not substitute a normal value.'),
        }
    return summary


def telemetry_receipt(rows: list[Reading], scenario: str, seed: int, at_second: int | None = None) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError('Unknown scenario')
    end = max(r.second for r in rows) if at_second is None else at_second
    return {
        'schema_version': 1, 'source': 'synthetic', 'scenario': scenario,
        'seed': seed, 'elapsed_seconds': end + 1,
        'assessment': summarize(rows, end),
        'nasa_context': {'title': 'NASA Environmental Control and Life Support Systems (ECLSS)',
                         'url': NASA_ECLSS,
                         'use': 'Research context for cabin monitoring variables; not a source of synthetic values.'},
        'assumptions': 'Illustrative independent channel state models and designed scenario perturbations; not physiological or life-support models.',
        'not_for_medical_or_flight_use': True,
        'real_sensor_data': False,
    }
