





def eva_progress(has_reference: bool, has_report: bool) -> tuple[int, str]:
    if not has_reference:
        return 1, 'Create a pre-EVA reference to begin.'
    if not has_report:
        return 2, 'Reference ready. Import or simulate post-EVA data.'
    return 3, 'Comparison ready. Review the evidence report.'


def homepage_summary(status: dict, scenario: str) -> tuple[str, str]:
    problems = [v['label'] for v in status.values() if v['quality'] == 'insufficient']
    if problems:
        return 'warning', 'Evidence needs checking: ' + ', '.join(problems) + '. Missing or stale readings are not treated as normal.'
    if status.get('cabin_co2', {}).get('trend') == 'rising':
        return 'info', 'Cabin CO₂ is rising in this simulation. Verify the sensor and investigate the trend; this is not a diagnosis or flight alarm.'
    if scenario == 'exercise':
        return 'info', 'Simulated activity affects crew measurements. The change is descriptive, not a medical conclusion.'
    return 'success', 'Simulated readings are available. This does not establish astronaut health or real sensor accuracy.'


def eva_plain_stage(has_before: bool, has_result: bool) -> tuple[str, str]:
    """Plain-language explanation, separate from the scientific assessment."""
    if not has_before:
        return 'Before spacewalk', 'Create the first reading for comparison.'
    if not has_result:
        return 'After spacewalk', 'Get new readings from the sensor simulator.'
    return 'Your results', 'Review what changed and which readings need checking.'


def eva_outcome(status: str) -> str:
    """No health or flight-readiness claims from synthetic measurements."""
    return {
        'insufficient_evidence': 'Not enough reliable data to compare the measurements.',
        'changes_observed': 'Some measurements are different from before the spacewalk.',
        'no_large_descriptive_change': 'Measurements look similar under the demo comparison rules.',
    }.get(status, 'Review the measurement details below.')
