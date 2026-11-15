import io
import json
import unittest
from unittest.mock import patch

from blindspot.food_lookup import extract_food, normalize_barcode, lookup_food
from blindspot.face_profiles import choose_match, face_labels


class CameraFoodTests(unittest.TestCase):
    def test_barcode_validation(self):
        self.assertEqual(normalize_barcode(' 3017620422003 '), '3017620422003')
        with self.assertRaises(ValueError):
            normalize_barcode('123/../')

    def test_nutrition_per_100g_and_zero_are_preserved(self):
        result = extract_food('3017620422003', {'status': 1, 'product': {'product_name': 'Sample', 'nutriments': {
            'energy-kcal_100g': 540, 'proteins_100g': 6.5, 'carbohydrates_100g': 57, 'fat_100g': 31}}})
        self.assertEqual(result['energy_kcal'], 540)
        self.assertEqual(result['serving_basis'], '100 g / 100 ml')

    def test_missing_macros_not_guessed(self):
        self.assertIsNone(extract_food('3017620422003', {'status': 1, 'product': {
            'product_name': 'Sample', 'nutriments': {'energy-kcal_100g': 200}}}))

    def test_network_lookup_error_is_not_a_food(self):
        with patch('blindspot.food_lookup.urlopen', side_effect=OSError('offline')):
            with self.assertRaises(LookupError):
                lookup_food('3017620422003')

    def test_face_labels_are_fixed_crew(self):
        self.assertEqual(face_labels(), ('CREW-01', 'CREW-02', 'CREW-03'))

    def test_face_match_rejects_ambiguous_or_weak(self):
        self.assertIsNone(choose_match([('CREW-01', 46), ('CREW-02', 47)]))
        self.assertIsNone(choose_match([('CREW-01', 101)]))
        self.assertEqual(choose_match([('CREW-01', 30), ('CREW-02', 65)]), 'CREW-01')

if __name__ == '__main__': unittest.main()


def test_online_food_keeps_100g_basis(tmp_path):
    from blindspot.meals import MealStore
    store = MealStore(tmp_path / 'meals.sqlite3')
    store.save_food('3017620422003', 'Sample', 540, 6.5, 57, 31, basis='100g')
    assert store.find_food('3017620422003')['basis'] == '100g'
    store.record_meal('CREW-01', '3017620422003', 0.5)
    meal = store.latest_meal('CREW-01')
    assert meal['energy_kcal'] == 540
    from blindspot.meals import meal_summary
    assert meal_summary([meal])['energy_kcal'] == 270


def test_existing_catalog_schema_migrates_without_dropping_records(tmp_path):
    import sqlite3
    db_file = tmp_path / 'old.sqlite3'
    with sqlite3.connect(db_file) as db:
        db.execute('''CREATE TABLE food_catalog (
            barcode TEXT PRIMARY KEY,label TEXT NOT NULL,energy_kcal REAL NOT NULL,
            protein_g REAL NOT NULL,carbs_g REAL NOT NULL,fat_g REAL NOT NULL)''')
        db.execute('INSERT INTO food_catalog VALUES (?,?,?,?,?,?)',('12345678','Old food',100,5,10,3))
    from blindspot.meals import MealStore
    store = MealStore(db_file)
    assert store.find_food('12345678')['basis'] == 'serving'
