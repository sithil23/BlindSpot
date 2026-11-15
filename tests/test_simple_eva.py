from blindspot.navigation import eva_plain_stage, eva_outcome


def test_simple_stage_is_clear_and_prioritizes_available_data():
    assert eva_plain_stage(False, False) == ('Before spacewalk', 'Create the first reading for comparison.')
    assert eva_plain_stage(True, False) == ('After spacewalk', 'Get new readings from the sensor simulator.')
    assert eva_plain_stage(True, True) == ('Your results', 'Review what changed and which readings need checking.')


def test_outcome_never_claims_medical_clearance():
    assert 'not enough' in eva_outcome('insufficient_evidence').lower()
    assert 'different' in eva_outcome('changes_observed').lower()
    assert 'similar' in eva_outcome('no_large_descriptive_change').lower()
    for status in ('insufficient_evidence', 'changes_observed', 'no_large_descriptive_change'):
        assert 'healthy' not in eva_outcome(status).lower()


def test_guided_eva_view_does_not_mutate_step_radio_state():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / 'blindspot' / 'ui.py').read_text()
    body = text.split('def eva_view():', 1)[1].split('def main():', 1)[0]
    assert "key='eva_step'" not in body
    assert 'st.session_state.eva_step' not in body
    assert 'Get readings from sensor simulator' in body
    assert 'Save before-spacewalk reading' in body
