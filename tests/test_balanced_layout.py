import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT/'blindspot/ui.py').read_text(encoding='utf-8')
CSS = (ROOT/'blindspot/assets/theme.css').read_text(encoding='utf-8')
DASHBOARD = UI.split('def multi_crew_live_dashboard():',1)[1].split('def _advance_eva(',1)[0]


def test_dashboard_has_compact_header_and_balanced_six_graph_grid():
    assert "st.markdown('### Live mission dashboard')" not in UI
    assert "st.markdown('### Mission status')" not in DASHBOARD
    assert 'st.columns(3, gap="medium")' in DASHBOARD
    assert 'chart_specs = [' in DASHBOARD
    assert 'for index, (entity, channel, title, unit) in enumerate(chart_specs):' in DASHBOARD
    assert 'with chart_columns[index % 3]:' in DASHBOARD


def test_status_console_remains_before_crew_cards():
    assert 'with warning_right:' in DASHBOARD
    assert DASHBOARD.index('with warning_right:') < DASHBOARD.index("st.markdown('### Crew')")
    assert 'voice_widget_html(flags)' in DASHBOARD


def test_clean_dense_style_keeps_square_corners_and_no_animations():
    assert 'animation: none !important' in CSS
    assert 'border-radius: 0px !important' in CSS
    assert '.dashboard-warning-entry' in CSS
    assert '.dashboard-section-label' in CSS


def test_source_compiles():
    ast.parse(UI)
