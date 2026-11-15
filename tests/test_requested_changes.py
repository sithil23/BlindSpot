import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_button_is_on_right():
    source = (ROOT / 'blindspot/ui.py').read_text(encoding='utf-8')
    assert '_, demo_button_column = st.columns([8, 2])' in source
    assert 'with demo_button_column:' in source
    ast.parse(source)


def test_warning_phrase_removed():
    source = (ROOT / 'blindspot/demo_controls.py').read_text(encoding='utf-8')
    assert 'Verify the measurement' not in source
    assert "f'DEMO · {selected_crew} {name}.'" in source
    ast.parse(source)
