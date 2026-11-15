from datetime import datetime, timezone, timedelta

from blindspot.meal_kiosk import MealFlow, resolve_food, persist_scanned_meal
from blindspot.meals import MealStore


def test_requires_two_matching_face_samples_before_accepting_barcode():
    flow = MealFlow(face_hits=2, barcode_hits=2)
    assert flow.observe('CREW-01', None, 0) is None
    assert flow.observe('CREW-01', None, 1) is None
    assert flow.active_crew == 'CREW-01'
    assert flow.observe(None, '3017620422003', 2) is None
    event = flow.observe(None, '3017620422003', 3)
    assert event == ('CREW-01', '3017620422003')


def test_rejects_ambiguous_identity_and_expires_before_barcode():
    flow = MealFlow(face_hits=2, barcode_hits=2, profile_ttl=10)
    flow.observe('CREW-01', None, 0)
    flow.observe('CREW-02', None, 1)
    assert flow.active_crew is None
    flow.observe('CREW-01', None, 2)
    flow.observe('CREW-01', None, 3)
    flow.observe(None, '3017620422003', 15)
    assert flow.active_crew is None
    assert flow.observe(None, '3017620422003', 16) is None


def test_barcode_must_be_stable_and_no_duplicate_event():
    flow = MealFlow(face_hits=2, barcode_hits=2, cooldown_seconds=180)
    for t in (1, 2):
        flow.observe('CREW-01', None, t)
    flow.observe(None, '12345678', 3)
    assert flow.observe(None, '12345678', 4) == ('CREW-01', '12345678')
    for t in (5, 6):
        flow.observe('CREW-01', None, t)
    flow.observe(None, '12345678', 7)
    assert flow.observe(None, '12345678', 8) is None


def test_unlisted_or_partial_product_is_not_saved(tmp_path):
    store = MealStore(tmp_path / 'meal.sqlite')
    assert resolve_food(store, '12345678', lookup=lambda _: None) is None
    assert store.latest_meal('CREW-01') is None


def test_online_product_saved_then_logged_once(tmp_path):
    store = MealStore(tmp_path / 'meal.sqlite')
    food = {'barcode': '3017620422003', 'label': 'Sample Food', 'energy_kcal': 120,
            'protein_g': 3, 'carbs_g': 15, 'fat_g': 4, 'serving_basis': '100 g / 100 ml'}
    assert resolve_food(store, '3017620422003', lookup=lambda _: food)['basis'] == '100g'
    now = datetime(2026, 11, 14, 16, tzinfo=timezone.utc)
    assert persist_scanned_meal(store, 'CREW-01', '3017620422003', now=now)
    assert not persist_scanned_meal(store, 'CREW-01', '3017620422003', now=now + timedelta(seconds=30))
    meal = store.latest_meal('CREW-01')
    assert meal['servings'] == 1
    assert meal['entry_method'] == 'auto_barcode'
    assert meal['needs_review'] == 1
    assert meal['basis'] == '100g'


def test_existing_meal_records_migrate_without_data_loss(tmp_path):
    import sqlite3
    file = tmp_path / 'old.sqlite'
    with sqlite3.connect(file) as conn:
        conn.executescript('''
          CREATE TABLE food_catalog(barcode TEXT PRIMARY KEY,label TEXT NOT NULL,
            energy_kcal REAL NOT NULL,protein_g REAL NOT NULL,carbs_g REAL NOT NULL,
            fat_g REAL NOT NULL,basis TEXT NOT NULL DEFAULT 'serving');
          CREATE TABLE meal_log(id INTEGER PRIMARY KEY AUTOINCREMENT,
            crew_id TEXT NOT NULL,barcode TEXT NOT NULL,servings REAL NOT NULL,
            eaten_at TEXT NOT NULL,energy_kcal REAL NOT NULL,protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,fat_g REAL NOT NULL);
        ''')
        conn.execute('INSERT INTO food_catalog VALUES (?,?,?,?,?,?,?)',('12345678','Legacy',130,1,2,3,'serving'))
        conn.execute('INSERT INTO meal_log(crew_id,barcode,servings,eaten_at,energy_kcal,protein_g,carbs_g,fat_g) VALUES (?,?,?,?,?,?,?,?)',
                     ('CREW-02','12345678',1,'2026-11-14T13:00:00+00:00',130,1,2,3))
    store = MealStore(file)
    saved = store.latest_meal('CREW-02')
    assert saved['energy_kcal'] == 130
    assert saved['entry_method'] == 'manual'
    assert saved['needs_review'] == 0


def test_ui_exposes_automatic_station_and_unverified_label():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1].joinpath('blindspot', 'ui.py').read_text()
    assert 'python meal_station.py' in source
    assert 'already >= 3' in source
    assert 'Auto-scanned; actual intake and portion not confirmed.' in source


def test_continuous_video_frames_do_not_erase_intermittent_detection():
    flow = MealFlow(face_hits=2, barcode_hits=2)
    flow.observe('CREW-01', None, 0.65)
    for i in range(12):
        flow.observe(None, None, .66 + i * .04)
    flow.observe('CREW-01', None, 1.30)
    assert flow.active_crew == 'CREW-01'
    flow.observe(None, '12345678', 1.4)
    for i in range(3):
        flow.observe(None, None, 1.41 + i * .02)
    assert flow.observe(None, '12345678', 1.53) == ('CREW-01', '12345678')
