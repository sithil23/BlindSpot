"""Regression tests for remote synthetic telemetry and safe import."""
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from blindspot.remote_api import build_payload, validate_payload, fetch_remote, RemoteTelemetryError
from remote_sensor_api import create_handler


def test_api_payload_can_be_checked_and_is_reproducible():
    a = build_payload('routine', seed=20, sequence=35)
    b = build_payload('routine', seed=20, sequence=35)
    assert {k:v for k,v in a.items() if k != "generated_at"} == {k:v for k,v in b.items() if k != "generated_at"}
    normalized = validate_payload(a)
    assert normalized['channels']['heart_rate']['unit'] == 'bpm'
    assert normalized['channels']['cabin_co2']['unit'] == 'ppm'
    assert normalized['source'] == 'synthetic_remote'


def test_missing_hr_is_never_filled_as_normal():
    payload = build_payload('hr_dropout', seed=42, sequence=100)
    normalized = validate_payload(payload)
    assert normalized['channels']['heart_rate']['value'] is None
    assert normalized['channels']['heart_rate']['quality'] == 'insufficient'


def test_client_rejects_malformed_or_stale_payloads():
    payload = build_payload('routine', 42, 20)
    payload['channels']['heart_rate']['unit'] = 'kelvin'
    with pytest.raises(RemoteTelemetryError):
        validate_payload(payload)
    payload = build_payload('routine', 42, 20)
    payload['generated_at'] = '2020-01-01T00:00:00+00:00'
    with pytest.raises(RemoteTelemetryError):
        validate_payload(payload)


def test_client_rejects_inconsistent_sensor_timestamps():
    payload = build_payload('routine', 42, 20)
    payload['channels']['spo2']['observed_at'] = None
    with pytest.raises(RemoteTelemetryError):
        validate_payload(payload)


def test_endpoint_refuses_requests_without_token():
    from io import BytesIO
    from http.server import HTTPServer
    from threading import Thread
    server = HTTPServer(('127.0.0.1', 0), create_handler('secret-test-token','routine',42))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.error
        import urllib.request
        url = f'http://127.0.0.1:{server.server_port}/v1/telemetry'
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(url, timeout=3)
        assert err.value.code == 401
        out = fetch_remote(url, 'secret-test-token', allow_http_local=True)
        assert out['source'] == 'synthetic_remote'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_remote_client_disallows_public_plain_http():
    with pytest.raises(RemoteTelemetryError):
        fetch_remote('http://example.com/v1/telemetry', 'test')


def test_api_supports_post_eva_export_with_identity_bound_to_request():
    from io import BytesIO
    from http.server import HTTPServer
    from threading import Thread
    from urllib.request import Request, urlopen
    from blindspot.eva import decode_assessment
    server = HTTPServer(('127.0.0.1', 0), create_handler('secret-test-token','routine',42, eva_scenario='exertion'))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/v1/eva/post?crew=CREW-01&eva=EVA-001'
        with urlopen(Request(url, headers={'Authorization': 'Bearer secret-test-token'}), timeout=3) as r:
            outcome = decode_assessment(r.read())
        assert outcome['phase'] == 'post' and outcome['participant'] == 'CREW-01'
        assert outcome['eva_id'] == 'EVA-001'
        assert outcome['scenario'] == 'exertion'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
