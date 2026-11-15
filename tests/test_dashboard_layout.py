"""Regression checks for the mission dashboard layout and alert treatment."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'blindspot' / 'ui.py'


def test_demo_button_uses_leftmost_column():
    source = SOURCE.read_text(encoding='utf-8')
    assert "demo_button_column, _ = st.columns([2, 8])" in source
    assert "with demo_button_column:" in source


def test_dashboard_uses_wide_responsive_page():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'layout="wide"' in source
    assert 'max-width: min(96vw, 1800px)' in source
    assert 'padding-left: clamp(1rem, 2vw, 2.5rem)' in source


def test_warning_shade_is_subtle_and_only_applied_for_warning():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'if any(flag["kind"] in ("critical", "warning", "feed", "evidence") for flag in flags):' in source
    assert 'dashboard-alert-shade' in source
    assert 'rgba(195, 38, 51, .07)' in source
    assert 'rgba(195, 38, 51, .045)' in source
    assert '<style class="dashboard-alert-shade">' in source


def test_module_parses():
    ast.parse(SOURCE.read_text(encoding='utf-8'))
