from pathlib import Path


def test_attention_drawer_is_available_on_dashboard():
    source = (Path(__file__).parents[1] / 'blindspot' / 'ui.py').read_text()
    assert 'rank_crew(shown_crew, flags)' in source
    assert "st.popover('Crew attention" in source
    assert "'Medical'" in source
    assert "'Rest'" in source
    assert "'Exercise'" in source
    assert "'Sleep'" in source


def test_compact_square_drawer_css():
    stylesheet = (Path(__file__).parents[1] / 'blindspot' / 'assets' / 'theme.css').read_text()
    assert '.crew-attention-item' in stylesheet
    assert 'border-radius: 0' in stylesheet
