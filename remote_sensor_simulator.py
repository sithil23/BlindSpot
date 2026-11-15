"""Independent demo sensor sender: export synthetic pre/post-EVA data to a JSON file.

Run this program on another computer after installing the BLINDSPOT project there.
Transfer the resulting JSON through the BLINDSPOT web import control.
This is an export/upload simulator, NOT a live authenticated network feed.
"""
import argparse
import json
from pathlib import Path
from blindspot.eva import SCENARIOS, build_assessment


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic EVA sensor exports')
    parser.add_argument('--crew', default='CREW-01')
    parser.add_argument('--eva', default='EVA-001')
    parser.add_argument('--phase', choices=['pre', 'post'], default='post')
    parser.add_argument('--scenario', choices=SCENARIOS, default='exertion')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', default='post-eva-sensors.json')
    args = parser.parse_args()
    result = build_assessment(args.crew, args.eva, args.phase, args.scenario, args.seed)
    path = Path(args.output)
    if path.exists():
        parser.error('Output file already exists; choose a new path')
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Created SYNTHETIC {args.phase.upper()} EVA export: {path} (scenario: {args.scenario})')


if __name__ == '__main__':
    main()
