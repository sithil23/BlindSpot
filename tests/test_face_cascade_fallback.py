from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from blindspot import face_profiles


def test_bundled_detector_available_when_opencv_data_missing():
    cv2 = SimpleNamespace(data=SimpleNamespace(haarcascades='C:/missing/cv2/data/'))
    path = face_profiles._cascade_path(cv2)
    assert path.is_file()
    assert path.name == 'haarcascade_frontalface_default.xml'
    assert Path('blindspot/assets/haarcascade_frontalface_default.xml').exists()


def test_bad_detector_does_not_call_detect_multi_scale(monkeypatch):
    import numpy as np
    class MissingCascade:
        def empty(self): return True
        def detectMultiScale(self, *a, **kw):
            raise AssertionError('must not call empty cascade')
    cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades='C:/missing/cv2/data/'),
        IMREAD_GRAYSCALE=0,
        imdecode=lambda raw, flags: np.zeros((140, 140), dtype=np.uint8),
        CascadeClassifier=lambda path: MissingCascade(),
    )
    monkeypatch.setattr(face_profiles, '_cv2', lambda: cv2)
    with pytest.raises(RuntimeError, match='face detector'):
        face_profiles._face_crop(b'bytes')
