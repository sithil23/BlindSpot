from datetime import datetime, timezone, timedelta

import pytest

from blindspot.meals import MealStore, meal_status, meal_summary


def test_unknown_meal_is_not_marked_missed():
    now = datetime(2025, 11, 14, 12, tzinfo=timezone.utc)
    assert meal_status(None, now)['state'] == 'no_record'


def test_reminder_starts_three_hours_after_suggested_meal():
    now = datetime(2025, 11, 14, 12, tzinfo=timezone.utc)
    old = now - timedelta(hours=7)
    assert meal_status(old, now, interval_hours=4, grace_hours=3)['state'] == 'reminder'
    assert meal_status(old + timedelta(seconds=1), now, 4, 3)['state'] == 'overdue'
    assert meal_status(now - timedelta(hours=3), now)['state'] == 'upcoming'
    assert meal_status(now + timedelta(minutes=10), now)['state'] == 'invalid'


def test_barcode_catalog_and_meal_records_persist(tmp_path):
    db = tmp_path / 'meals.db'
    store = MealStore(db)
    store.save_food('012345678905', 'Sample labelled food', 240, 12, 30, 8)
    assert store.find_food('012345678905')['energy_kcal'] == 240
    when = datetime(2025, 11, 14, 12, tzinfo=timezone.utc)
    store.record_meal('CREW-02', '012345678905', 0.5, when)
    assert MealStore(db).latest_meal('CREW-02')['eaten_at'] == when.isoformat()
    summary = meal_summary(MealStore(db).meal_history('CREW-02', since=when - timedelta(days=1)))
    assert summary['energy_kcal'] == pytest.approx(120)
    assert summary['protein_g'] == pytest.approx(6)


def test_invalid_and_missing_food_never_get_logged(tmp_path):
    store = MealStore(tmp_path / 'meals.db')
    with pytest.raises(ValueError):
        store.record_meal('CREW-01', '00000000000', 1)
    with pytest.raises(ValueError):
        store.save_food('x', 'food', -4, 2, 1, 0)
    store.save_food('SAMPLE', 'Sample', 10, 0, 2, 0)
    with pytest.raises(ValueError):
        store.record_meal('CREW-01', 'SAMPLE', 0)


def test_saved_nutrition_not_changed_by_catalog_edits(tmp_path):
    store = MealStore(tmp_path / 'meals.sqlite')
    store.save_food('BARCODE-1', 'Food', 200, 12, 20, 3)
    store.record_meal('CREW-01', 'BARCODE-1', 1.5, datetime(2025, 1, 1, tzinfo=timezone.utc))
    store.save_food('BARCODE-1', 'Updated label', 400, 24, 20, 3)
    totals = meal_summary(store.meal_history('CREW-01'))
    assert totals['energy_kcal'] == 300
    assert totals['protein_g'] == 18
