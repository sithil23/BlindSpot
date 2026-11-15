"""Guard against returning demo controls to the main dashboard layout."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'blindspot' / 'ui.py'


def test_demo_controls_live_in_floating_popover_not_expander():
    source = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(source)
    dashboard = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'multi_crew_live_dashboard')
    calls = [node for node in ast.walk(dashboard) if isinstance(node, ast.Call)]
    assert any(isinstance(node.func, ast.Attribute) and node.func.attr == 'popover' and node.args and isinstance(node.args[0], ast.Constant) and 'Demo' in str(node.args[0].value) for node in calls)
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == 'expander' and node.args and isinstance(node.args[0], ast.Constant) and 'Demo controls' in str(node.args[0].value) for node in calls)


def test_all_demo_inputs_are_inside_popover_and_clear_is_callback():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    dashboard = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'multi_crew_live_dashboard')
    def is_demo_popover(expr):
        return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == 'popover'
    popup = [node for node in ast.walk(dashboard) if isinstance(node, ast.With) and any(is_demo_popover(item.context_expr) for item in node.items)]
    assert len(popup) == 1
    calls = [node for child in popup[0].body for node in ast.walk(child) if isinstance(node, ast.Call)]
    assert sum(isinstance(call.func, ast.Attribute) and call.func.attr == 'selectbox' for call in calls) == 2
    assert any(isinstance(call.func, ast.Attribute) and call.func.attr == 'button' and any(keyword.arg == 'on_click' for keyword in call.keywords) for call in calls)
