from pathlib import Path


def test_dashboard_renders_meals_and_uses_saved_meal_status():
    src = Path(__file__).parents[1] / 'blindspot' / 'ui.py'
    text = src.read_text(encoding='utf-8')
    assert 'meal_panel(meal_db, meal_records)' in text
    assert 'meal_status(record[\'eaten_at\'])' in text
    assert "elif choice == \"Food Management\":" in text
    assert "def food_management_view():" in text
    assert "'Recognize crew'" in text
    assert "'Read barcode from photo'" in text
    assert "'Confirm crew, food and save meal'" in text
    assert "'food-catalog-form'" in text
    assert 'No meal recorded' in text
    assert 'Member, you should eat now' in text
    assert "meal_db = None" in text


def test_radiation_and_crew_followup_still_present():
    text = (Path(__file__).parents[1] / 'blindspot' / 'ui.py').read_text()
    assert "st.markdown('### Crew follow-up')" in text
    assert "st.markdown('### Radiation')" in text
    assert "st.markdown('### Sensor trends')" in text
