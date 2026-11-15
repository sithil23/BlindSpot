"""Local, continuously running meal scanning station (not a clinical identity system)."""

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from blindspot.face_profiles import enrolled_counts, recognize
from blindspot.food_lookup import lookup_food
from blindspot.meals import CREW_IDS, MealStore


class MealFlow:
    def __init__(self, face_hits=2, barcode_hits=2, profile_ttl=45, cooldown_seconds=180):
        self.face_hits = face_hits
        self.barcode_hits = barcode_hits
        self.profile_ttl = profile_ttl
        self.cooldown_seconds = cooldown_seconds
        self.active_crew = None
        self.active_since = 0
        self.face_candidate = None
        self.face_count = 0
        self.face_seen_at = None
        self.barcode_seen_at = None
        self.barcode_candidate = None
        self.barcode_count = 0
        self.last_logged = {}

    def observe(self, face, barcode, now):
        if self.active_crew and now - self.active_since > self.profile_ttl:
            self.reset()
        if face not in (None, *CREW_IDS):
            face = None
        if face and face != self.active_crew:
            if self.active_crew:
                self.reset()
            recent = self.face_seen_at is not None and now - self.face_seen_at <= 3
            self.face_count = self.face_count + 1 if recent and face == self.face_candidate else 1
            self.face_candidate = face
            self.face_seen_at = now
            if self.face_count >= self.face_hits:
                self.active_crew = face
                self.active_since = now
                self.barcode_candidate = None
                self.barcode_count = 0
                self.barcode_seen_at = None
        elif face and face == self.active_crew:
            self.active_since = now

        if not self.active_crew or not barcode:
            return None
        recent = self.barcode_seen_at is not None and now - self.barcode_seen_at <= 2
        self.barcode_count = self.barcode_count + 1 if recent and barcode == self.barcode_candidate else 1
        self.barcode_candidate = barcode
        self.barcode_seen_at = now
        if self.barcode_count < self.barcode_hits:
            return None
        crew = self.active_crew
        self.reset()
        key = crew, barcode
        if now - self.last_logged.get(key, -float('inf')) < self.cooldown_seconds:
            return None
        self.last_logged[key] = now
        return key

    def reset(self):
        self.active_crew = None
        self.face_candidate = None
        self.face_count = 0
        self.face_seen_at = None
        self.barcode_candidate = None
        self.barcode_count = 0
        self.barcode_seen_at = None


def resolve_food(store, barcode, lookup=lookup_food):
    cached = store.find_food(barcode)
    if cached:
        return cached
    product = lookup(barcode)
    if product is None:
        return None
    basis = '100g' if product['serving_basis'] == '100 g / 100 ml' else 'serving'
    store.save_food(barcode, product['label'], product['energy_kcal'], product['protein_g'],
                    product['carbs_g'], product['fat_g'], basis=basis)
    return store.find_food(barcode)


def persist_scanned_meal(store, crew, barcode, now=None, dedupe_seconds=180):
    now = now or datetime.now(timezone.utc)
    previous = store.latest_meal(crew)
    if previous and previous['barcode'] == barcode:
        age = now - datetime.fromisoformat(previous['eaten_at'])
        if timedelta(0) <= age < timedelta(seconds=dedupe_seconds):
            return False
    store.record_meal(crew, barcode, 1.0, eaten_at=now,
                      entry_method='auto_barcode', needs_review=True)
    return True


def read_video_barcode(frame):
    try:
        import zxingcpp
    except ImportError as exc:
        raise RuntimeError('Install zxing-cpp to scan barcodes') from exc
    results = zxingcpp.read_barcodes(frame)
    digits = {result.text for result in results
              if result.text and result.text.isascii() and result.text.isdigit() and 6 <= len(result.text) <= 18}
    return next(iter(digits)) if len(digits) == 1 else None


def read_video_face(frame, cv2):
    small = cv2.resize(frame, (640, int(640 * frame.shape[0] / frame.shape[1]))) if frame.shape[1] > 640 else frame
    ok, buf = cv2.imencode('.jpg', small, [int(cv2.IMWRITE_JPEG_QUALITY), 83])
    if not ok:
        return None
    try:
        return recognize(buf.tobytes())
    except (ValueError, RuntimeError):
        return None


def run(camera=0):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('Install opencv-contrib-python and numpy for the camera station') from exc
    from blindspot.face_profiles import _cv2
    _cv2()
    if not any(count >= 3 for count in enrolled_counts().values()):
        raise RuntimeError('Enroll three face photos for at least one crew member in More > Food Management')

    store = MealStore()
    camera = cv2.VideoCapture(camera, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError('Could not open the local webcam')
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
    flow = MealFlow()
    last_face_check = 0
    last_face = None
    last_barcode_check = 0
    seen_code = None
    notice = 'Show your face to begin'
    notice_expiry = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                notice = 'Camera read failed'
                time.sleep(.15)
                continue
            now = time.monotonic()
            if now - last_face_check >= .65:
                last_face_check = now
                last_face = read_video_face(frame, cv2)
            if now - last_barcode_check >= .12:
                last_barcode_check = now
                try:
                    seen_code = read_video_barcode(frame)
                except (ValueError, RuntimeError) as exc:
                    notice = str(exc)
                    notice_expiry = now + 5
                    seen_code = None

            event = flow.observe(last_face if now == last_face_check else None,
                                 seen_code if now == last_barcode_check else None, now)
            if event:
                crew, barcode = event
                try:
                    food = resolve_food(store, barcode)
                    if not food:
                        notice = f'Unknown barcode {barcode} - register in More tab'
                    elif persist_scanned_meal(store, crew, barcode):
                        notice = f'{crew}: {food["label"][:32]} recorded - review quantity'
                    else:
                        notice = f'{crew}: recent duplicate barcode ignored'
                except (LookupError, OSError, ValueError, sqlite3.Error) as exc:
                    notice = f'Food lookup failed: {str(exc)[:65]}'
                notice_expiry = time.monotonic() + 9

            if notice_expiry < now:
                notice = (f'{flow.active_crew}: show food barcode' if flow.active_crew
                          else 'Show your face to begin')
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 94), (23, 37, 58), -1)
            cv2.putText(frame, 'BLINDSPOT - AUTO MEAL STATION', (16, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, .68, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, notice[:96], (16, 66), cv2.FONT_HERSHEY_SIMPLEX,
                        .53, (205, 235, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, 'ESC to close | Auto-logs 1 catalog unit; confirm actual intake later',
                        (12, frame.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, .42, (255,255,255), 1)
            cv2.imshow('BLINDSPOT meal station', frame)
            if (cv2.waitKey(1) & 0xFF) == 27:
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
