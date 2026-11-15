"""Regression checks for the uncluttered BLINDSPOT UI."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'blindspot' / 'ui.py'


def test_user_interface_avoids_caption_widgets():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    captions = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'caption' and isinstance(n.func.value, ast.Name) and n.func.value.id == 'st']
    assert captions == [], f'Found distracting caption widgets on lines {captions}'


def test_unnecessary_progress_and_disclaimer_copy_removed():
    code = SOURCE.read_text(encoding='utf-8')
    assert 'Current progress:' not in code
    assert 'Demo only: sensor readings are simulated.' not in code
    assert 'research demonstration using synthetic telemetry' not in code


def test_result_graph_has_no_caption():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    image_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'image']
    assert not any(k.arg == 'caption' for n in image_calls for k in n.keywords)
