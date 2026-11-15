import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'blindspot' / 'ui.py'
CSS = ROOT / 'blindspot' / 'assets' / 'theme.css'


def test_svg_charts_render_as_html_not_images():
    source = UI.read_text(encoding='utf-8')
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'image']
    assert all(isinstance(node.func.value, ast.Name) and node.func.value.id == 'preview' for node in calls), 'chart images must be rendered inline; camera preview may still use images'
    assert 'st.html(' in source


def test_dashboard_warning_panel_has_right_column():
    source = UI.read_text(encoding='utf-8')
    method = source.split('def multi_crew_live_dashboard():', 1)[1].split('def _advance_eva(', 1)[0]
    assert 'warning_left, warning_right = st.columns(' in method
    assert 'with warning_right:' in method
    assert 'dashboard-warning-panel' in method
    assert method.index('with warning_right:') < method.index("st.markdown('#### Astronauts')")


def test_theme_flat_and_no_motion_or_image_overlay():
    css = CSS.read_text(encoding='utf-8')
    assert 'animation: none !important' in css
    assert 'transition: none !important' in css
    assert '.plain-svg-chart svg' in css
