"""Contract tests for simulated crew/cabin telemetry and evidence-first decisions."""
from blindspot.telemetry import CHANNELS, SCENARIOS, generate_mission, summarize, telemetry_receipt


def test_replay_is_deterministic_but_time_series_moves_smoothly():
    a = generate_mission('routine', seed=42, duration=60)
    b = generate_mission('routine', seed=42, duration=60)
    assert a == b
    hr = [r.value for r in a if r.channel == 'heart_rate']
    assert len(set(hr)) > 10
    assert max(abs(x-y) for x,y in zip(hr,hr[1:])) < 7


def test_all_channels_have_units_and_timestamp_and_synthetic_provenance():
    rows = generate_mission('routine', seed=1, duration=20)
    assert set(CHANNELS) == {r.channel for r in rows}
    assert all(r.unit == CHANNELS[r.channel].unit for r in rows)
    assert all(r.source == 'synthetic' and r.second >= 0 for r in rows)


def test_rising_cabin_co2_is_observed_not_medically_diagnosed():
    records = generate_mission('co2_rise', seed=3, duration=120)
    series = [r.value for r in records if r.channel == 'cabin_co2']
    assert series[-1] > series[0] + 500
    status = summarize(records)
    assert status['cabin_co2']['quality'] == 'adequate'
    assert status['cabin_co2']['trend'] == 'rising'
    assert 'diagnos' not in str(status).lower()


def test_sensor_failure_is_not_replaced_with_normal_values():
    data = generate_mission('hr_dropout', seed=5, duration=60)
    status = summarize(data)
    assert status['heart_rate']['quality'] == 'insufficient'
    assert status['heart_rate']['value'] is None
    assert status['spo2']['quality'] == 'adequate'
    assert 'missing' in status['heart_rate']['reasons']


def test_stale_telemetry_does_not_count_as_current():
    status = summarize(generate_mission('hr_stale', seed=1, duration=60))
    assert status['heart_rate']['quality'] == 'insufficient'
    assert status['heart_rate']['value'] is None
    assert 'stale' in status['heart_rate']['reasons']


def test_receipt_includes_provenance_not_claims_of_live_telemetry():
    rows = generate_mission('exercise', seed=9, duration=40)
    receipt = telemetry_receipt(rows, 'exercise', 9)
    assert receipt['source'] == 'synthetic'
    assert receipt['scenario'] == 'exercise'
    assert receipt['nasa_context']['url'].startswith('https://www.nasa.gov/')
    assert receipt['not_for_medical_or_flight_use'] is True
    assert receipt['assessment']['heart_rate']['quality'] == 'adequate'


def test_named_scenarios_exist():
    assert {'routine', 'exercise', 'co2_rise', 'hr_dropout', 'hr_stale'} <= set(SCENARIOS)
