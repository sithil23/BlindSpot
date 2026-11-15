import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'blindspot' / 'ui.py').read_text(encoding='utf-8')
CSS = (ROOT / 'blindspot' / 'assets' / 'theme.css').read_text(encoding='utf-8')


def test_primary_navigation_uses_buttons_not_radio():
    main = UI.split('def main():', 1)[1]
    assert 'st.radio("Go to"' not in main
    assert 'st.button(label, key=f"nav-' in main
    assert 'on_click=_set_main_page' in main
    assert 'selected_page = st.session_state.get("main_page"' in main


def test_navigation_callback_exists():
    assert 'def _set_main_page(page: str):' in UI
    ast.parse(UI)


def test_six_sensor_charts_present_with_larger_two_column_layout():
    dash = UI.split('def multi_crew_live_dashboard():', 1)[1].split('def _advance_eva(', 1)[0]
    assert 'chart_columns = st.columns(2,' in dash
    assert 'chart_columns[index % 2]' in dash
    assert "'heart_rate'" in dash and "'spo2'" in dash and "'respiration'" in dash
    assert "'cabin_co2'" in dash and "'cabin_o2'" in dash
    assert "'acceleration'" in dash
    assert 'line_chart_svg(' in dash


def test_alert_text_is_large_and_easy_to_read():
    assert '.dashboard-warning-entry strong' in CSS
    assert 'font-size: 1.25rem' in CSS
    assert 'font-size: 1.5rem' in CSS
