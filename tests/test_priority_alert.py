from blindspot.crew_attention import priority_alert, crew_report


def test_flagged_person_has_pulse_and_report():
    item = {'crew_id': 'CREW-03', 'level': 'Flagged', 'score': 3, 'state': 'Review sensor reading',
            'stats': {'heart_rate': 112, 'spo2': 91, 'respiration': 21, 'body_temp': 37.2}}
    alert = priority_alert(item)
    assert alert['highlight'] is True
    assert alert['message'] == 'Crew review requested'
    report = crew_report(item)
    assert report['crew_id'] == 'CREW-03'
    assert report['delivery_status'] == 'not_sent'
    assert report['synthetic'] is True


def test_data_gap_is_not_a_medical_flag():
    item = {'crew_id': 'CREW-02', 'level': 'Data missing', 'score': 2, 'state': 'Check sensor feed', 'stats': {}}
    assert priority_alert(item)['highlight'] is False
    assert crew_report(item)['delivery_status'] == 'not_sent'


def test_normal_feed_not_highlighted():
    item = {'crew_id': 'CREW-01', 'level': 'No crew flags', 'score': 0, 'state': 'No flagged crew readings', 'stats': {}}
    assert priority_alert(item)['highlight'] is False
