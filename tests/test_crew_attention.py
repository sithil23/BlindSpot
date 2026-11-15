from blindspot.crew_attention import rank_crew


def feed(hr=74, spo2=98, respiration=15, temp=36.7, scenario='routine'):
    values = {'heart_rate': hr, 'spo2': spo2, 'respiration': respiration, 'body_temp': temp}
    return {'scenario': scenario, 'channels': {key: {'value': value, 'quality': 'adequate'} for key, value in values.items()}}


def test_demo_warning_pushes_selected_astronaut_to_top():
    crew = {'CREW-01': feed(), 'CREW-02': feed(), 'CREW-03': feed()}
    flags = [{'kind': 'warning', 'message': 'DEMO · CREW-03 blood oxygen reading is low.'}]
    result = rank_crew(crew, flags)
    assert [x['crew_id'] for x in result] == ['CREW-03', 'CREW-01', 'CREW-02']
    assert result[0]['medical'] == 'Review flagged reading'
    assert result[0]['stats']['spo2'] == 98


def test_missing_feed_never_appears_normal():
    crew = {'CREW-01': feed(), 'CREW-02': None, 'CREW-03': feed()}
    result = rank_crew(crew, [])
    assert result[0]['crew_id'] == 'CREW-02'
    assert result[0]['state'] == 'Check sensor feed'
    assert result[0]['stats']['heart_rate'] is None
    assert result[0]['medical'] == 'Not assessable'


def test_missing_channel_is_a_data_quality_issue():
    crew = {'CREW-01': feed(), 'CREW-02': feed(), 'CREW-03': feed()}
    crew['CREW-02']['channels']['heart_rate']['quality'] = 'insufficient'
    result = rank_crew(crew, [])
    assert result[0]['crew_id'] == 'CREW-02'
    assert result[0]['stats']['heart_rate'] is None
    assert result[0]['state'] == 'Check measurement'


def test_no_sleep_or_rest_claim_from_telemetry():
    result = rank_crew({'CREW-01': feed(scenario='exercise')}, [])
    assert result[0]['sleep'] == 'Not assessed'
    assert result[0]['rest'] == 'Not assessed'
    assert result[0]['exercise'] == 'Exercise context recorded'


def test_warning_for_other_crew_not_attributed():
    crew = {'CREW-01': feed(), 'CREW-02': feed(), 'CREW-03': feed()}
    flags = [{'kind': 'trend', 'message': 'Habitat B simulated cabin CO₂ is rising.'}]
    result = rank_crew(crew, flags)
    assert all(x['state'] == 'No flagged crew readings' for x in result)
    assert len(result) == 3


def test_bad_quality_with_warning_does_not_produce_medical_assertion():
    crew = {'CREW-01': None}
    flags = [{'kind': 'warning', 'message': 'DEMO · CREW-01 feed unavailable. Cannot inject a reading.'}]
    result = rank_crew(crew, flags)
    assert result[0]['medical'] == 'Not assessable'


def test_similar_crew_id_cannot_steal_other_crew_warning():
    feeds = {'CREW-01': feed(), 'CREW-010': feed()}
    flags = [{'kind': 'warning', 'message': 'DEMO · CREW-010 heart-rate reading is high.'}]
    ranked = rank_crew(feeds, flags)
    assert ranked[0]['crew_id'] == 'CREW-010'
    assert ranked[1]['state'] == 'No flagged crew readings'
