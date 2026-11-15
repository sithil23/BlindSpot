from datetime import datetime, timezone
import copy
import pytest

from blindspot.radiation import build_radiation_payload, validate_radiation_payload, radiation_flags, radiation_exposure, apply_radiation_demo


def test_cumulative_dose_is_monotonic_and_rate_matches_integration():
    a = build_radiation_payload(elapsed_seconds=120, seed=12)
    b = build_radiation_payload(elapsed_seconds=180, seed=12)
    assert b['crews']['CREW-01']['cumulative_dose_uSv'] >= a['crews']['CREW-01']['cumulative_dose_uSv']
    assert radiation_exposure([10, None, 20], 60) is None
    assert radiation_exposure([10, 20], 60) == pytest.approx(.25)


def test_missing_radiation_dose_does_not_fake_cumulative_total():
    p = build_radiation_payload(80)
    p['crews']['CREW-01']['quality'] = 'insufficient'
    p['crews']['CREW-01']['dose_equivalent_rate_uSv_h'] = None
    p['crews']['CREW-01']['cumulative_dose_uSv'] = None
    assert validate_radiation_payload(p)['crews']['CREW-01']['cumulative_dose_uSv'] is None
    assert any('CREW-01' in f['message'] for f in radiation_flags(p))


def test_source_and_units_cannot_change_silently():
    p = build_radiation_payload(40)
    q = copy.deepcopy(p)
    q['crews']['CREW-02']['unit'] = 'uGy/h'
    with pytest.raises(ValueError): validate_radiation_payload(q)
    q = copy.deepcopy(p)
    q['source'] = 'real_dosimeter'
    with pytest.raises(ValueError): validate_radiation_payload(q)


def test_radiation_demo_is_copy_only_and_explicit():
    p = build_radiation_payload(50)
    q, flags = apply_radiation_demo(p, 'radiation_event', 'CREW-02')
    assert q['crews']['CREW-02']['dose_equivalent_rate_uSv_h'] > p['crews']['CREW-02']['dose_equivalent_rate_uSv_h']
    assert p['crews']['CREW-02']['quality'] == 'adequate'
    assert flags and 'DEMO' in flags[0]['message']
    q2, f2 = apply_radiation_demo(p, 'radiation_sensor_loss', 'CREW-02')
    assert q2['crews']['CREW-02']['dose_equivalent_rate_uSv_h'] is None
    assert q2['crews']['CREW-02']['cumulative_dose_uSv'] is None
    assert f2


def test_future_stale_and_negative_dose_rejected():
    p = build_radiation_payload(40)
    p['generated_at'] = '2020-01-01T00:00:00+00:00'
    with pytest.raises(ValueError): validate_radiation_payload(p)
    p = build_radiation_payload(40)
    p['crews']['CREW-01']['cumulative_dose_uSv'] = -3
    with pytest.raises(ValueError): validate_radiation_payload(p)


def test_authenticated_radiation_api_fetches_two_separate_simulators():
    from http.server import HTTPServer
    from threading import Thread
    from remote_sensor_api import create_handler
    from blindspot.remote_api import fetch_radiation_remote, RemoteTelemetryError
    import urllib.error
    import urllib.request

    servers = []
    try:
        for seed in (12, 97):
            server = HTTPServer(('127.0.0.1', 0), create_handler('long-secret-123', 'routine', seed))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            servers.append((server, thread))
        urls = [f'http://127.0.0.1:{server.server_port}/v1/telemetry' for server, _ in servers]
        first = fetch_radiation_remote(urls[0], 'long-secret-123', allow_http_local=True)
        second = fetch_radiation_remote(urls[1], 'long-secret-123', allow_http_local=True)
        assert first['source'] == 'synthetic_radiation'
        assert first['crews']['CREW-01']['dose_equivalent_rate_uSv_h'] != second['crews']['CREW-01']['dose_equivalent_rate_uSv_h']
        with pytest.raises(RemoteTelemetryError):
            fetch_radiation_remote(urls[0], 'bad-password', allow_http_local=True)
        with pytest.raises(RemoteTelemetryError):
            fetch_radiation_remote('http://example.com/v1/telemetry', 'long-secret-123')
    finally:
        for server, thread in servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
