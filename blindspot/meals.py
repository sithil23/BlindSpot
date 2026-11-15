import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

CREW_IDS = ('CREW-01', 'CREW-02', 'CREW-03')


def _utc(dt):
    if dt.tzinfo is None:
        raise ValueError('A timezone-aware timestamp is required')
    return dt.astimezone(timezone.utc)


def meal_status(last_eaten, now=None, interval_hours=4, grace_hours=3):
    now = _utc(now or datetime.now(timezone.utc))
    if last_eaten is None:
        return {'state': 'no_record', 'next_meal': None, 'reminder_at': None}
    if isinstance(last_eaten, str):
        last_eaten = datetime.fromisoformat(last_eaten)
    last_eaten = _utc(last_eaten)
    next_meal = last_eaten + timedelta(hours=interval_hours)
    reminder = next_meal + timedelta(hours=grace_hours)
    if last_eaten > now:
        state = 'invalid'
    elif now >= reminder:
        state = 'reminder'
    elif now >= next_meal:
        state = 'overdue'
    else:
        state = 'upcoming'
    return {'state': state, 'next_meal': next_meal, 'reminder_at': reminder}


def meal_summary(rows):
    totals = {name: 0.0 for name in ('energy_kcal', 'protein_g', 'carbs_g', 'fat_g')}
    for row in rows:
        for name in totals:
            totals[name] += float(row[name]) * float(row['servings'])
    return totals


class MealStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('BLINDSPOT_MEAL_DB', 'blindspot_meals.sqlite3'))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS food_catalog (
                    barcode TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    energy_kcal REAL NOT NULL,
                    protein_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    basis TEXT NOT NULL DEFAULT 'serving'
                );
                CREATE TABLE IF NOT EXISTS meal_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crew_id TEXT NOT NULL,
                    barcode TEXT NOT NULL REFERENCES food_catalog(barcode),
                    servings REAL NOT NULL,
                    eaten_at TEXT NOT NULL,
                    energy_kcal REAL NOT NULL,
                    protein_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    basis TEXT NOT NULL DEFAULT 'serving',
                    entry_method TEXT NOT NULL DEFAULT 'manual',
                    needs_review INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS meal_by_crew_time ON meal_log(crew_id,eaten_at DESC);
            ''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(food_catalog)')}
            if 'basis' not in columns:
                db.execute("ALTER TABLE food_catalog ADD COLUMN basis TEXT NOT NULL DEFAULT 'serving'")
            log_columns = {row[1] for row in db.execute('PRAGMA table_info(meal_log)')}
            for name, ddl in [('basis', "TEXT NOT NULL DEFAULT 'serving'"),
                              ('entry_method', "TEXT NOT NULL DEFAULT 'manual'"),
                              ('needs_review', 'INTEGER NOT NULL DEFAULT 0')]:
                if name not in log_columns:
                    db.execute(f'ALTER TABLE meal_log ADD COLUMN {name} {ddl}')

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def save_food(self, barcode, label, energy_kcal, protein_g, carbs_g, fat_g, basis='serving'):
        barcode = str(barcode).strip()
        label = str(label).strip()
        amounts = [float(n) for n in (energy_kcal, protein_g, carbs_g, fat_g)]
        if not (3 <= len(barcode) <= 48 and barcode.isascii() and barcode.isprintable()) or not label or len(label) > 120:
            raise ValueError('Enter a valid barcode and food label')
        if any(not (0 <= value <= 100000) for value in amounts):
            raise ValueError('Nutrient values must be nonnegative, finite numbers')
        if basis not in ('serving', '100g'):
            raise ValueError('Unknown nutrition serving basis')
        with self._connect() as db:
            db.execute('INSERT INTO food_catalog (barcode,label,energy_kcal,protein_g,carbs_g,fat_g,basis) VALUES (?,?,?,?,?,?,?) '
                       'ON CONFLICT(barcode) DO UPDATE SET label=excluded.label, energy_kcal=excluded.energy_kcal, '
                       'protein_g=excluded.protein_g, carbs_g=excluded.carbs_g, fat_g=excluded.fat_g, basis=excluded.basis',
                       (barcode, label, *amounts, basis))
        return barcode

    def find_food(self, barcode):
        with self._connect() as db:
            row = db.execute('SELECT * FROM food_catalog WHERE barcode=?', (str(barcode).strip(),)).fetchone()
        return dict(row) if row else None

    def record_meal(self, crew_id, barcode, servings, eaten_at=None, *, entry_method='manual', needs_review=False):
        if crew_id not in CREW_IDS:
            raise ValueError('Unknown astronaut')
        servings = float(servings)
        if entry_method not in ('manual', 'auto_barcode'):
            raise ValueError('Unsupported meal entry method')
        if not 0 < servings <= 20:
            raise ValueError('Servings must be greater than zero and no more than 20')
        eaten_at = _utc(eaten_at or datetime.now(timezone.utc))
        if eaten_at > datetime.now(timezone.utc) + timedelta(minutes=1):
            raise ValueError('Future meal times cannot be recorded')
        barcode = str(barcode).strip()
        with self._connect() as db:
            food = db.execute('SELECT * FROM food_catalog WHERE barcode=?', (barcode,)).fetchone()
            if food is None:
                raise ValueError('Barcode not in the food catalog; add the label first')
            db.execute('INSERT INTO meal_log(crew_id,barcode,servings,eaten_at,energy_kcal,protein_g,carbs_g,fat_g,basis,entry_method,needs_review) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (crew_id, barcode, servings, eaten_at.isoformat(),
                        food['energy_kcal'], food['protein_g'], food['carbs_g'], food['fat_g'],
                        food['basis'], entry_method, int(needs_review)))

    def latest_meal(self, crew_id):
        if crew_id not in CREW_IDS:
            raise ValueError('Unknown astronaut')
        with self._connect() as db:
            row = db.execute('SELECT m.*, f.label FROM meal_log m JOIN food_catalog f USING(barcode) '
                             'WHERE m.crew_id=? ORDER BY m.eaten_at DESC,m.id DESC LIMIT 1',
                             (crew_id,)).fetchone()
        return dict(row) if row else None

    def meal_history(self, crew_id, since=None):
        if crew_id not in CREW_IDS:
            raise ValueError('Unknown astronaut')
        since = _utc(since or datetime(1970, 1, 1, tzinfo=timezone.utc))
        with self._connect() as db:
            rows = db.execute('SELECT m.*, f.label '
                              'FROM meal_log m JOIN food_catalog f USING(barcode) '
                              'WHERE m.crew_id=? AND m.eaten_at >= ? ORDER BY m.eaten_at DESC,m.id DESC',
                              (crew_id, since.isoformat())).fetchall()
        return [dict(row) for row in rows]
