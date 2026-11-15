import json
import subprocess
import sys
from pathlib import Path

from blindspot.eva import decode_assessment


def test_cli_creates_transferable_sensor_file(tmp_path):
    root = Path(__file__).resolve().parents[1]
    dest = tmp_path / 'post.json'
    proc = subprocess.run([sys.executable, str(root / 'remote_sensor_simulator.py'),
                           '--crew', 'CREW-01', '--eva', 'EVA-001', '--scenario',
                           'sensor_loss', '--output', str(dest)], cwd=root,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = decode_assessment(dest.read_bytes())
    assert payload['phase'] == 'post'
    assert payload['measurements']['spo2']['value'] is None
    again = subprocess.run([sys.executable, str(root / 'remote_sensor_simulator.py'),
                            '--output', str(dest)], cwd=root, capture_output=True, text=True)
    assert again.returncode != 0
