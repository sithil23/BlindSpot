



from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlencode, urlunsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from blindspot.telemetry import CHANNELS, SCENARIOS, generate_mission, summarize


class RemoteTelemetryError(ValueError):
    """Remote synthetic data is unavailable, invalid, or insufficiently trustworthy."""


class _NoRedirect(HTTPRedirectHandler):
    """Never forward an API bearer token to an unexpected redirect destination."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RemoteTelemetryError('Remote API redirects are not permitted')


_opener = build_opener(_NoRedirect())


def build_payload(scenario: str = 'routine', seed: int = 42, sequence: int = 119) -> dict:
    if scenario not in SCENARIOS or not isinstance(sequence, int) or not 0 <= sequence < 3600:
        raise RemoteTelemetryError('Invalid simulated scenario or sequence')
    rows = generate_mission(scenario, seed, max(120, sequence + 1))
    result = summarize(rows, sequence)
    latest = {r.channel: r for r in rows if r.second == sequence}
    return {
        'schema': 'blindspot.synthetic.telemetry.v1',
        'source': 'synthetic_remote',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'sequence': sequence,
        'scenario': scenario,
        'channels': {
            key: {
                'value': result[key]['value'],
                'unit': ch.unit,
                'quality': result[key]['quality'],
                'trend': result[key]['trend'],
                'reasons': result[key]['reasons'],
                'observed_at': latest[key].observed_at,
                'label': ch.label,
                'domain': ch.domain,
            }
            for key, ch in CHANNELS.items()
        },
        'notice': 'SYNTHETIC demonstration data only; not medical or flight-use telemetry.',
    }


def validate_payload(payload: object, *, max_age_seconds: int = 30) -> dict:
    if not isinstance(payload, dict) or payload.get('schema') != 'blindspot.synthetic.telemetry.v1' or payload.get('source') != 'synthetic_remote':
        raise RemoteTelemetryError('Unknown telemetry source or format')
    try:
        when = datetime.fromisoformat(payload['generated_at'])
        if when.tzinfo is None:
            raise ValueError('missing timezone')
        age = (datetime.now(timezone.utc) - when).total_seconds()
        if age < -10 or age > max_age_seconds:
            raise RemoteTelemetryError('Remote telemetry is stale or clock is out of sync')
        seq = payload['sequence']
        if type(seq) is not int or not 0 <= seq < 3600:
            raise ValueError('invalid sequence')
        if payload.get('scenario') not in SCENARIOS:
            raise ValueError('invalid scenario')
        values = payload['channels']
        if not isinstance(values, dict) or set(values) != set(CHANNELS):
            raise ValueError('incomplete or unexpected channels')
        for key, ch in CHANNELS.items():
            r = values[key]
            if not isinstance(r, dict) or r.get('unit') != ch.unit or r.get('quality') not in ('adequate', 'insufficient'):
                raise ValueError(f'invalid metadata: {key}')
            if r.get('label') != ch.label or r.get('domain') != ch.domain:
                raise ValueError(f'invalid channel description: {key}')
            observed_at = r.get('observed_at')
            if observed_at is not None and (type(observed_at) is not int or observed_at < 0 or observed_at > seq):
                raise ValueError(f'invalid sensor timestamp: {key}')
            if observed_at is None and r['quality'] == 'adequate':
                raise ValueError(f'missing timestamp marked adequate: {key}')
            val = r.get('value')
            if r['quality'] == 'adequate':
                if type(val) not in (float, int) or not math.isfinite(val):
                    raise ValueError(f'invalid reading: {key}')
                if seq - observed_at > 3:
                    raise ValueError(f'stale sensor marked adequate: {key}')
            elif val is not None:
                raise ValueError(f'insufficient sensor presented a numeric value: {key}')
            if not isinstance(r.get('reasons'), list) or not isinstance(r.get('trend'), str):
                raise ValueError(f'bad quality metadata: {key}')
    except (KeyError, TypeError, ValueError) as exc:
        raise RemoteTelemetryError(f'Invalid telemetry: {exc}') from exc
    return payload


def fetch_remote(url: str, token: str, *, allow_http_local: bool = False) -> dict:
    """Fetch one small authenticated JSON snapshot; no interactive user-supplied URL."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' and not (allow_http_local and parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
        raise RemoteTelemetryError('Remote endpoint requires HTTPS (or explicitly configured loopback HTTP)')
    if not parsed.hostname or not token:
        raise RemoteTelemetryError('Remote API address/token is missing')
    req = Request(url, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
    try:
        with _opener.open(req, timeout=4) as response:
            if response.status != 200:
                raise RemoteTelemetryError('Remote sensor service returned an error')
            raw = response.read(65537)
            if len(raw) > 65536:
                raise RemoteTelemetryError('Remote sensor response too large')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteTelemetryError(f'Remote sensor service unavailable: {exc}') from exc
    try:
        return validate_payload(json.loads(raw))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RemoteTelemetryError(f'Invalid remote sensor JSON: {exc}') from exc


def fetch_post_eva(url: str, token: str, crew: str, eva: str, *, allow_http_local: bool = False) -> dict:
    """Fetch strictly validated post-EVA synthetic assessment for a selected crew/EVA."""
    from urllib.parse import urlencode, urlunsplit
    from blindspot.eva import decode_assessment
    parsed = urlsplit(url)
    if parsed.scheme != 'https' and not (allow_http_local and parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
        raise RemoteTelemetryError('Remote EVA API requires HTTPS or loopback HTTP')
    if not parsed.hostname or not token:
        raise RemoteTelemetryError('Remote EVA API configuration missing')
    if not crew or not eva or len(crew) > 40 or len(eva) > 40:
        raise RemoteTelemetryError('Invalid crew/EVA identifier')
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, '/v1/eva/post', urlencode({'crew': crew, 'eva': eva}), ''))
    request = Request(endpoint, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
    try:
        with _opener.open(request, timeout=4) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise RemoteTelemetryError('Oversized EVA response')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteTelemetryError(f'Remote EVA simulator unavailable: {exc}') from exc
    try:
        result = decode_assessment(raw)
    except ValueError as exc:
        raise RemoteTelemetryError(f'Invalid EVA sensor export: {exc}') from exc
    if (result['participant'], result['eva_id'], result['phase']) != (crew, eva, 'post'):
        raise RemoteTelemetryError('EVA sensor response identity mismatch')
    return result


CREW_CODES = ('CREW-01', 'CREW-02', 'CREW-03')


def build_crew_payload(scenario: str, seed: int, sequence: int, crew_id: str) -> dict:
    """Create an independently seeded synthetic crew snapshot for a named profile."""
    if crew_id not in CREW_CODES:
        raise RemoteTelemetryError('Unknown simulated crew profile')
    payload = build_payload(scenario, seed + 101 * (CREW_CODES.index(crew_id) + 1), sequence)
    payload['crew_id'] = crew_id
    return payload


def validate_crew_payload(payload: object, crew_id: str) -> dict:
    if crew_id not in CREW_CODES or not isinstance(payload, dict) or payload.get('crew_id') != crew_id:
        raise RemoteTelemetryError('Crew identity mismatch')
    return validate_payload(payload)


def fetch_crew_remote(url: str, token: str, crew_id: str, *, allow_http_local: bool = False) -> dict:
    """Fetch named crew data from the same trusted API origin as the habitat feed."""
    if crew_id not in CREW_CODES:
        raise RemoteTelemetryError('Unknown crew identifier')
    parsed = urlsplit(url)
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, '/v1/crew', urlencode({'crew': crew_id}), ''))
    result = fetch_remote(endpoint, token, allow_http_local=allow_http_local)
    return validate_crew_payload(result, crew_id)


def fetch_radiation_remote(url: str, token: str, *, allow_http_local: bool = False) -> dict:
    from blindspot.radiation import validate_radiation_payload
    parsed = urlsplit(url)
    if parsed.scheme != 'https' and not (allow_http_local and parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
        raise RemoteTelemetryError('Radiation endpoint requires HTTPS or loopback HTTP')
    if not parsed.hostname or not token:
        raise RemoteTelemetryError('Radiation API not configured')
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, '/v1/radiation', '', ''))
    request = Request(endpoint, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
    try:
        with _opener.open(request, timeout=4) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise RemoteTelemetryError('Radiation response too large')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteTelemetryError(f'Radiation feed unavailable: {exc}') from exc
    try:
        return validate_radiation_payload(json.loads(raw))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RemoteTelemetryError(f'Invalid radiation data: {exc}') from exc
