from blindspot.navigation import eva_progress, homepage_summary


def test_eva_steps_move_forward_only_when_reference_exists():
    assert eva_progress(False, False) == (1, 'Create a pre-EVA reference to begin.')
    assert eva_progress(True, False) == (2, 'Reference ready. Import or simulate post-EVA data.')
    assert eva_progress(True, True) == (3, 'Comparison ready. Review the evidence report.')


def test_home_summary_prioritizes_evidence_problems():
    status = {
        'hr': {'label': 'Heart rate', 'quality': 'insufficient', 'trend': 'stable'},
        'cabin_co2': {'label': 'CO₂', 'quality': 'adequate', 'trend': 'rising'},
    }
    assert homepage_summary(status, 'routine')[0] == 'warning'


def test_home_summary_warns_about_rising_co2_not_diagnosis():
    status = {'cabin_co2': {'label': 'Cabin CO₂', 'quality': 'adequate', 'trend': 'rising'}}
    level, message = homepage_summary(status, 'routine')
    assert level == 'info' and 'not a diagnosis' in message.lower()
