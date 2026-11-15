from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_crew_followup_always_rendered_without_popover():
    code = (ROOT / 'blindspot/ui.py').read_text(encoding='utf-8')
    assert 'rank_crew(shown_crew, flags)' in code
    assert "st.popover('Crew attention" not in code
    assert 'st.columns(3, gap="small")' in code
    assert 'Crew follow-up' in code


def test_crew_followup_keeps_all_categories():
    code = (ROOT / 'blindspot/ui.py').read_text(encoding='utf-8')
    for text in ("('Medical', item['medical'])", "('Rest', item['rest'])", "('Exercise', item['exercise'])", "('Sleep', item['sleep'])"):
        assert text in code
