from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "blindspot" / "ui.py"
CSS = ROOT / "blindspot" / "assets" / "theme.css"


def test_food_management_has_no_explanatory_captions():
    section = UI.read_text(encoding="utf-8").split("def food_management_view():", 1)[1].split("@st.fragment", 1)[0]
    assert "st.caption(" not in section
    assert "st.markdown('#### 3. Review and save')" not in section
    assert "Select a member and look up a barcode." not in section
    assert "placeholder='Scan or enter an EAN / UPC barcode'" not in section


def test_flat_styles_cover_drawers_portals_and_dialogs():
    css = CSS.read_text(encoding="utf-8")
    assert '[data-baseweb="popover"]' in css
    assert '[data-baseweb="modal"]' in css
    assert '[data-testid="stDialog"]' in css
    assert "transition-duration: 0s !important" in css
    assert "border-radius: 0 !important" in css


def test_manual_camera_workflow_kept():
    section = UI.read_text(encoding="utf-8").split("def food_management_view():", 1)[1].split("@st.fragment", 1)[0]
    for text in ("Register crew member", "Recognize member", "Read barcode number", "Find product online", "Save meal"):
        assert text in section
