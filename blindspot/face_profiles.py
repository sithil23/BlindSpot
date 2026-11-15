import io
import os
from pathlib import Path

from blindspot.meals import CREW_IDS


def face_labels():
    return CREW_IDS


def choose_match(candidates, max_distance=70, min_margin=14):
    # LBPH distances are not probabilities; reject borderline or ambiguous matches.
    items = sorted((float(distance), name) for name, distance in candidates if name in CREW_IDS)
    if not items or items[0][0] > max_distance:
        return None
    if len(items) > 1 and items[1][0] - items[0][0] < min_margin:
        return None
    return items[0][1]


def profile_dir():
    # Store biometric data locally, outside Git-tracked code.
    return Path(os.environ.get('BLINDSPOT_FACE_DIR', 'data/face_profiles'))


def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('Camera recognition needs opencv-contrib-python and numpy') from exc
    if not hasattr(cv2, 'face') or not hasattr(cv2.face, 'LBPHFaceRecognizer_create'):
        raise RuntimeError('Install opencv-contrib-python (not opencv-python) to enable recognition')
    return cv2


def _cascade_path(cv2):
    name = 'haarcascade_frontalface_default.xml'
    bundled = Path(__file__).resolve().parent / 'assets' / name
    if bundled.is_file():
        return bundled
    location = getattr(getattr(cv2, 'data', None), 'haarcascades', None)
    if location:
        candidate = Path(location) / name
        if candidate.is_file():
            return candidate
    raise RuntimeError('OpenCV face detector is missing; reinstall the BLINDSPOT detector file')


def _face_crop(image_bytes):
    cv2 = _cv2()
    import numpy as np
    raw = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError('Camera image could not be read')
    if img.shape[0] > 2000 or img.shape[1] > 2000:
        img = cv2.resize(img, (min(img.shape[1], 1280), min(img.shape[0], 1280)))
    cascade = cv2.CascadeClassifier(str(_cascade_path(cv2)))
    if cascade.empty():
        raise RuntimeError('OpenCV face detector could not load; check the BLINDSPOT detector file')
    faces = cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(75,75))
    if len(faces) != 1:
        raise ValueError('Show exactly one face clearly to the camera')
    x,y,w,h = faces[0]
    return cv2.equalizeHist(cv2.resize(img[y:y+h,x:x+w], (120,120)))


def _store_path(root=None):
    root = Path(root) if root else profile_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != 'nt':
        root.chmod(0o700)
    return root / 'enrolled_faces.npz'


def enroll(crew_id, image_bytes, root=None):
    if crew_id not in CREW_IDS:
        raise ValueError('Unknown crew profile')
    crop = _face_crop(image_bytes)
    import numpy as np
    target = _store_path(root)
    samples = {}
    if target.exists():
        with np.load(target, allow_pickle=False) as data:
            samples = {key: data[key] for key in data.files if key in CREW_IDS}
    samples[crew_id] = np.concatenate((samples.get(crew_id, np.empty((0,120,120),dtype=np.uint8)), crop[None]))[-10:]
    buf = io.BytesIO()
    np.savez_compressed(buf, **samples)
    tmp = target.with_suffix('.tmp')
    try:
        tmp.write_bytes(buf.getvalue())
        os.replace(tmp, target)
        if os.name != 'nt':
            target.chmod(0o600)
    finally:
        tmp.unlink(missing_ok=True)
    return len(samples[crew_id])


def enrolled_counts(root=None):
    import numpy as np
    target = _store_path(root)
    if not target.exists():
        return {}
    with np.load(target, allow_pickle=False) as data:
        return {key: len(data[key]) for key in data.files if key in CREW_IDS}


def recognize(image_bytes, root=None):
    cv2 = _cv2()
    import numpy as np
    crop = _face_crop(image_bytes)
    target = _store_path(root)
    if not target.exists():
        raise ValueError('Enroll crew members before using face recognition')
    images, ids = [], []
    with np.load(target, allow_pickle=False) as data:
        for index, name in enumerate(CREW_IDS):
            if name in data and len(data[name]) >= 3:
                images.extend(data[name])
                ids.extend([index] * len(data[name]))
    if len(set(ids)) < 1:
        raise ValueError('Enroll at least three images for a crew member')
    model = cv2.face.LBPHFaceRecognizer_create()
    model.train(images, np.array(ids, dtype=np.int32))
    idx, distance = model.predict(crop)
    name = CREW_IDS[idx]
    if distance > 70:
        return None
    # Compare the candidate against every enrolled crew to avoid ambiguous IDs.
    candidates = []
    with np.load(target, allow_pickle=False) as data:
        for other in CREW_IDS:
            if other not in data or len(data[other]) < 3:
                continue
            model_one = cv2.face.LBPHFaceRecognizer_create()
            model_one.train(list(data[other]), np.zeros(len(data[other]), dtype=np.int32))
            _, dist = model_one.predict(crop)
            candidates.append((other, dist))
    return choose_match(candidates)


def delete_profile(crew_id, root=None):
    if crew_id not in CREW_IDS:
        raise ValueError('Unknown crew profile')
    import numpy as np
    target = _store_path(root)
    if not target.exists():
        return
    with np.load(target, allow_pickle=False) as data:
        rest = {key: data[key] for key in data.files if key != crew_id and key in CREW_IDS}
    if not rest:
        target.unlink()
    else:
        buf = io.BytesIO()
        np.savez_compressed(buf, **rest)
        tmp = target.with_suffix('.tmp')
        try:
            tmp.write_bytes(buf.getvalue())
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
