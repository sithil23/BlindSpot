from blindspot.demo_controls import demo_options, apply_demo, trend_history, gravity_reading
from blindspot.dashboard import dashboard_flags
from blindspot.remote_api import build_crew_payload


def test_demo_low_oxygen_only_changes_selected_crew_and_is_explicitly_synthetic():
    one = build_crew_payload('routine', 42, 75, 'CREW-01')
    two = build_crew_payload('routine', 42, 75, 'CREW-02')
    simulated, flags = apply_demo({'CREW-01':one,'CREW-02':two}, {}, 'low_spo2', 'CREW-01')
    assert simulated['CREW-01']['channels']['spo2']['value'] < one['channels']['spo2']['value']
    assert simulated['CREW-02']['channels']['spo2']['value'] == two['channels']['spo2']['value']
    assert one['channels']['spo2']['value'] > simulated['CREW-01']['channels']['spo2']['value']
    assert flags and all('DEMO' in f['message'] for f in flags)


def test_demo_scenarios_cover_crew_and_habitat_and_gravity():
    crew = {'CREW-01':build_crew_payload('routine', 42, 80, 'CREW-01')}
    cabin = {'Habitat A':build_crew_payload('routine', 42, 80, 'CREW-01')}
    for scenario in demo_options():
        simulated, flags = apply_demo(crew, cabin, scenario, 'CREW-01')
        assert isinstance(simulated, dict) and isinstance(flags, list)
    assert gravity_reading('microgravity', 5) == 0.0
    assert gravity_reading('routine', 5) >= 0


def test_sensor_failure_never_makes_missing_data_look_good():
    crew = {'CREW-01':build_crew_payload('routine', 42, 75, 'CREW-01')}
    result, flags = apply_demo(crew, {}, 'sensor_loss', 'CREW-01')
    assert result['CREW-01']['channels']['heart_rate']['value'] is None
    assert result['CREW-01']['channels']['heart_rate']['quality'] == 'insufficient'
    assert any('sensor' in f['message'].lower() for f in flags)
    assert dashboard_flags(result, {})


def test_chart_history_deduplicates_refresh_and_drops_bad_values():
    history=[]
    history=trend_history(history, 'CREW-01', 'heart_rate', 72, 100, 5)
    history=trend_history(history, 'CREW-01', 'heart_rate', 77, 100, 5)
    history=trend_history(history, 'CREW-01', 'heart_rate', None, 101, 5)
    assert len(history)==2
    assert history[0]['value']==72
    assert history[1]['value'] is None


def test_disconnected_feed_cannot_be_overridden_to_fake_healthy_readings():
    simulated, flags = apply_demo({'CREW-01':None}, {}, 'low_spo2', 'CREW-01')
    assert simulated['CREW-01'] is None
    assert flags and 'unavailable' in flags[0]['message'].lower()
