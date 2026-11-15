import pytest
from blindspot.dashboard import dashboard_flags, crew_summary
from blindspot.remote_api import build_crew_payload, validate_crew_payload, RemoteTelemetryError


def test_crew_payloads_differ_and_are_synthetic():
    one = validate_crew_payload(build_crew_payload('routine', 42, 55, 'CREW-01'), 'CREW-01')
    two = validate_crew_payload(build_crew_payload('routine', 42, 55, 'CREW-02'), 'CREW-02')
    assert one['crew_id'] == 'CREW-01'
    assert one['channels']['heart_rate']['value'] != two['channels']['heart_rate']['value']
    assert one['source'] == 'synthetic_remote'


def test_wrong_crew_rejected():
    with pytest.raises(RemoteTelemetryError):
        validate_crew_payload(build_crew_payload('routine', 42, 70, 'CREW-01'), 'CREW-03')


def test_crew_dropouts_do_not_look_normal():
    payload = validate_crew_payload(build_crew_payload('hr_dropout', 42, 100, 'CREW-02'), 'CREW-02')
    assert payload['channels']['heart_rate']['quality'] == 'insufficient'
    assert crew_summary(payload)['heart_rate'] is None
    flags = dashboard_flags({'CREW-02': payload}, {})
    assert any(f['kind'] == 'evidence' for f in flags)


def test_second_feed_down_is_flagged_not_filled():
    flags = dashboard_flags({'CREW-01': build_crew_payload('routine', 42, 50, 'CREW-01'), 'CREW-03': None}, {})
    assert any(f['kind'] == 'feed' and 'CREW-03' in f['message'] for f in flags)


def test_co2_rising_is_investigate_not_diagnosis():
    habitat = {'feed-2': build_crew_payload('co2_rise', 42, 110, 'CREW-03')}
    flags = dashboard_flags({}, habitat)
    assert any(f['kind'] == 'trend' for f in flags)
    assert not any('diagnos' in f['message'].lower() for f in flags)


def test_two_independent_http_servers_feed_three_astronauts():
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from remote_sensor_api import create_handler
    from blindspot.remote_api import fetch_crew_remote, fetch_remote
    servers, threads = [], []
    try:
        for scenario, seed in [('routine', 42), ('co2_rise', 99)]:
            srv = ThreadingHTTPServer(('127.0.0.1', 0), create_handler('testing-secret-token', scenario, seed))
            th = Thread(target=srv.serve_forever, daemon=True)
            th.start()
            servers.append(srv)
            threads.append(th)
        urls = [f'http://127.0.0.1:{s.server_port}/v1/telemetry' for s in servers]
        crew_1 = fetch_crew_remote(urls[0], 'testing-secret-token', 'CREW-01', allow_http_local=True)
        crew_2 = fetch_crew_remote(urls[0], 'testing-secret-token', 'CREW-02', allow_http_local=True)
        crew_3 = fetch_crew_remote(urls[1], 'testing-secret-token', 'CREW-03', allow_http_local=True)
        habitat_2 = fetch_remote(urls[1], 'testing-secret-token', allow_http_local=True)
        assert len({c['crew_id'] for c in (crew_1, crew_2, crew_3)}) == 3
        assert crew_3['scenario'] == 'co2_rise'
        assert habitat_2['scenario'] == 'co2_rise'
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for th in threads:
            th.join(timeout=3)
