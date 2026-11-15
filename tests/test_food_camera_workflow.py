from pathlib import Path

UI = Path(__file__).resolve().parents[1] / 'blindspot' / 'ui.py'


def test_one_shared_camera_for_meal_photo():
    source = UI.read_text(encoding='utf-8')
    section = source.split('def food_management_view():', 1)[1].split('@st.fragment', 1)[0]
    assert section.count("st.camera_input('Meal camera'") == 1
    assert "food-face-photo" not in section
    assert "food-barcode-camera" not in section
    assert "scan_barcode(photo.getvalue())" in section
    assert "recognize(photo.getvalue())" in section


def test_registration_is_single_explicit_control_three_samples():
    source = UI.read_text(encoding='utf-8')
    section = source.split('def food_management_view():', 1)[1].split('@st.fragment', 1)[0]
    assert "st.button('Register crew member'" in section
    assert "if already < 3:" in section
    assert "food-face-consent" in section


def test_no_automatic_meal_station_prompts():
    source = UI.read_text(encoding='utf-8')
    section = source.split('def food_management_view():', 1)[1].split('@st.fragment', 1)[0]
    assert 'python meal_station.py' not in section
    assert 'Automatic meal station' not in section
    assert "st.button('Save meal'" in section
