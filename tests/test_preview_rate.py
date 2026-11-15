from blindspot.preview_rate import should_update


def test_preview_updates_are_throttled_without_delaying_first_frame():
    assert should_update(0.0, -1.0, 0.5)
    assert not should_update(0.1, 0.0, 0.5)
    assert not should_update(0.49, 0.0, 0.5)
    assert should_update(0.5, 0.0, 0.5)


def test_progress_interval_can_be_different_from_preview_interval():
    assert should_update(0.26, 0.0, 0.25)
    assert not should_update(0.26, 0.0, 0.5)
