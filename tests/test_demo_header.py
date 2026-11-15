import ast
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / 'blindspot' / 'ui.py'


def test_demo_popover_is_in_page_header_not_below_dashboard_title():
    source = UI.read_text(encoding='utf-8')
    tree = ast.parse(source)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    dashboard = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'multi_crew_live_dashboard')
    assert 'with st.popover' in ast.get_source_segment(source, main)
    assert 'with st.popover' not in ast.get_source_segment(source, dashboard)
    assert 'with header_right:' in ast.get_source_segment(source, main)


def test_warning_visuals_stay_in_dashboard():
    text = UI.read_text(encoding='utf-8')
    assert 'dashboard-alert-shade' in text
    assert 'voice_widget_html(flags)' in text
