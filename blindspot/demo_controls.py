



from __future__ import annotations

from copy import deepcopy
import math

SCENARIOS = {
    'routine': 'Normal feeds',
    'low_spo2': 'Low blood oxygen (SpO₂)',
    'fast_hr': 'Fast heart rate',
    'slow_hr': 'Slow heart rate',
    'fast_breathing': 'Fast breathing',
    'high_temp': 'High body temperature',
    'high_co2': 'High cabin CO₂',
    'low_o2': 'Low cabin oxygen',
    'sensor_loss': 'Heart-rate sensor disconnect',
    'gravity_shift': 'Acceleration change',
    'microgravity': 'Microgravity demonstration',
    'radiation_event': 'Radiation dose-rate increase',
    'radiation_sensor_loss': 'Radiation dosimeter disconnect',
}


def demo_options():
    return tuple(SCENARIOS)


def gravity_reading(scenario: str, second: int) -> float:

    if scenario == 'microgravity':
        return 0.0
    if scenario == 'gravity_shift':
        return round(0.02 + 0.17 * (1 + math.sin(second / 6)) / 2, 3)
    return round(0.02 + 0.003 * math.sin(second / 8), 3)


def apply_demo(crew: dict, habitat: dict, scenario: str, selected_crew: str) -> tuple[dict, list[dict[str, str]]]:
    """Return copied displays and explicit synthetic demo flags, never mutate API payloads."""
    if scenario not in SCENARIOS:
        raise ValueError('Unknown demo scenario')
    combined = {**crew, **habitat}
    result = deepcopy(combined)
    if scenario == 'routine':
        return result, []
    flags: list[dict[str, str]] = []
    c = result.get(selected_crew)
    crew_scenarios = {'low_spo2', 'fast_hr', 'slow_hr', 'fast_breathing', 'high_temp', 'sensor_loss'}
    if scenario in crew_scenarios:
        if c is None:
            flags.append({'kind': 'warning', 'message': f'DEMO · {selected_crew} feed unavailable. Cannot inject a reading.'})
            return result, flags
        key = {'low_spo2': 'spo2', 'fast_breathing': 'respiration', 'high_temp': 'body_temp'}.get(scenario, 'heart_rate')
        ch = c['channels'][key]
        if ch['quality'] != 'adequate' and scenario != 'sensor_loss':
            flags.append({'kind': 'warning', 'message': f'DEMO · {selected_crew} {key} unavailable; no invented value.'})
            return result, flags
        if scenario == 'sensor_loss':
            ch.update(value=None, quality='insufficient', reasons=['missing'], trend='unknown', observed_at=None)
            flags.append({'kind': 'warning', 'message': f'DEMO · {selected_crew} heart-rate sensor disconnected. Check the feed.'})
        else:
            ch['value'] = {'low_spo2': 88.0, 'fast_hr': 132.0, 'slow_hr': 43.0, 'fast_breathing': 29.0, 'high_temp': 38.5}[scenario]
            ch['trend'] = 'falling' if scenario in ('low_spo2', 'slow_hr') else 'rising'
            name = {'low_spo2': 'blood oxygen reading is low', 'fast_hr': 'heart-rate reading is high', 'slow_hr': 'heart-rate reading is low', 'fast_breathing': 'breathing rate is high', 'high_temp': 'body temperature reading is high'}[scenario]
            flags.append({'kind': 'warning', 'message': f'DEMO · {selected_crew} {name}.'})
    elif scenario in ('high_co2', 'low_o2'):

        name = next((k for k in ('Habitat B', 'Habitat A') if k in result and result[k] is not None), None)
        if name is None:
            flags.append({'kind': 'warning', 'message': 'DEMO · Cabin feed unavailable. Cannot inject a reading.'})
            return result, flags
        key = 'cabin_co2' if scenario == 'high_co2' else 'cabin_o2'
        ch = result[name]['channels'][key]
        if ch['quality'] != 'adequate':
            flags.append({'kind': 'warning', 'message': f'DEMO · {name} sensor unavailable; no invented value.'})
            return result, flags
        ch['value'] = 2800.0 if scenario == 'high_co2' else 18.2
        ch['trend'] = 'rising' if scenario == 'high_co2' else 'falling'
        desc = 'CO₂ is high' if scenario == 'high_co2' else 'oxygen reading is low'
        flags.append({'kind': 'warning', 'message': f'DEMO · {name} {desc}. Check cabin conditions.'})
    elif scenario in ('radiation_event', 'radiation_sensor_loss'):
        pass
    elif scenario in ('gravity_shift', 'microgravity'):
        label = 'changing acceleration' if scenario == 'gravity_shift' else 'microgravity conditions'
        flags.append({'kind': 'context', 'message': f'DEMO · Simulated {label}; not a live gravity sensor.'})
    return result, flags


def trend_history(history: list[dict], entity: str, channel: str, value: float | None,
                  sequence: int, limit: int = 60) -> list[dict]:
    """Append one new sample per source sequence; preserve gaps as None."""
    if not isinstance(sequence, int) or sequence < 0 or limit < 1:
        raise ValueError('Invalid history configuration')
    if value is not None and (not isinstance(value, (float, int)) or not math.isfinite(value)):
        value = None
    records = list(history)
    if records and records[-1]['sequence'] == sequence and records[-1]['entity'] == entity and records[-1]['channel'] == channel:
        return records
    records.append({'entity': entity, 'channel': channel, 'sequence': sequence, 'value': value})
    return records[-limit:]
