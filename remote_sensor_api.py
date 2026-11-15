



from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
import time
from urllib.parse import urlsplit, parse_qs
from blindspot.eva import SCENARIOS as EVA_SCENARIOS, build_assessment

from blindspot.remote_api import build_payload, build_crew_payload, CREW_CODES
from blindspot.radiation import build_radiation_payload
from blindspot.telemetry import SCENARIOS


def create_handler(token: str, scenario: str, seed: int, eva_scenario: str = "exertion"):
    if not token or len(token) < 12:
        raise ValueError('Use a token of at least 12 characters')
    if scenario not in SCENARIOS or eva_scenario not in EVA_SCENARIOS:
        raise ValueError('Unsupported scenario')
    started_at = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/healthz':
                return self.respond(200, {'service': 'blindspot-synthetic-sensor', 'status': 'ok'})
            if path not in ('/v1/telemetry', '/v1/eva/post', '/v1/crew', '/v1/radiation'):
                return self.respond(404, {'error': 'not found'})
            supplied = self.headers.get('Authorization', '')
            if not hmac.compare_digest(supplied, f'Bearer {token}'):
                return self.respond(401, {'error': 'authorization required'})
            if path == '/v1/radiation':
                return self.respond(200, build_radiation_payload(int(time.monotonic() - started_at), seed))
            if path == '/v1/crew':
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                crew = query.get('crew', [])
                if len(crew) != 1 or crew[0] not in CREW_CODES:
                    return self.respond(400, {'error': 'valid crew code required'})
                sequence = min(119, int(time.monotonic() - started_at) % 120)
                return self.respond(200, build_crew_payload(scenario, seed, sequence, crew[0]))
            if path == '/v1/eva/post':
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                crew, eva = query.get('crew', []), query.get('eva', [])
                if len(crew) != 1 or len(eva) != 1:
                    return self.respond(400, {'error': 'crew and eva codes required'})
                try:
                    return self.respond(200, build_assessment(crew[0], eva[0], 'post', eva_scenario, seed))
                except ValueError:
                    return self.respond(400, {'error': 'invalid crew or eva code'})
            # A repeating 120-second simulation supplies time-varying readings; sequence

            sequence = min(119, int(time.monotonic() - started_at) % 120)
            return self.respond(200, build_payload(scenario, seed, sequence))

        def respond(self, code, payload):
            content = json.dumps(payload, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description='BLINDSPOT synthetic sensor API (no real sensors)')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--scenario', choices=list(SCENARIOS), default='routine')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--eva-scenario', choices=list(EVA_SCENARIOS), default='exertion')
    args = parser.parse_args()
    token = os.getenv('BLINDSPOT_SENSOR_TOKEN', '')
    if not token:
        parser.error('Set BLINDSPOT_SENSOR_TOKEN to a long random secret')
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    server = ThreadingHTTPServer((args.host, args.port), create_handler(token, args.scenario, args.seed, args.eva_scenario))
    print(f'Synthetic sensor API listening on {args.host}:{args.port} ({args.scenario})')
    print('Authenticated endpoints: GET /v1/telemetry, GET /v1/crew?crew=CREW-01, GET /v1/eva/post?crew=CREW-01&eva=EVA-001, GET /v1/radiation')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
