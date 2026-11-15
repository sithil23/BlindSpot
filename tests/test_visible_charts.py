from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'blindspot' / 'ui.py').read_text(encoding='utf-8')
CHART = ROOT / 'blindspot' / 'plain_charts.py'


def test_dashboard_uses_html_component_not_streamlit_html_for_svg():
    dashboard = UI.split('def multi_crew_live_dashboard():', 1)[1].split('def _advance_eva(', 1)[0]
    assert 'components.html(chart_document(' in dashboard
    assert 'st.html(f\'<div class="plain-svg-chart">{line_chart_svg(' not in dashboard
    assert 'height=236' in dashboard


def test_chart_document_is_a_standalone_embeddable_html_page():
    spec = importlib.util.spec_from_file_location('plain_charts', CHART)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    html = module.chart_document([72.1, 73.0, None, 78.2], 'Heart rate', 'bpm')
    assert '<!doctype html>' in html.lower()
    assert '<svg ' in html
    assert '<polyline ' in html
    assert '<meta name="viewport"' in html
    assert 'overflow:hidden' in html.replace(' ', '')
    assert 'toolbar' not in html.lower()


def test_chart_document_preserves_missing_sample_breaks():
    spec = importlib.util.spec_from_file_location('plain_charts', CHART)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    svg = module.line_chart_svg([70, 71, None, 73, 74], 'Heart', 'bpm')
    assert svg.count('<polyline ') == 2
    assert 'NaN' not in svg


def test_python_parses():
    ast.parse(UI)
