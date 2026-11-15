from types import SimpleNamespace

import pytest

from blindspot.camera import CameraUnavailable, capture, landmark_distance
from blindspot.models import Protocol


def hand():
    points = [SimpleNamespace(x=0.5, y=0.5) for _ in range(21)]
    points[5] = SimpleNamespace(x=0.4, y=0.6)
    points[17] = SimpleNamespace(x=0.6, y=0.6)
    points[4] = SimpleNamespace(x=0.5, y=0.4)
    points[8] = SimpleNamespace(x=0.5, y=0.3)
    return points


def test_distance_uses_pixel_aspect_ratio_and_palm_width():
    assert landmark_distance(hand(), 640, 480) == pytest.approx(0.375)


def test_outside_frame_and_degenerate_palms_are_unusable():
    points = hand()
    points[8].x = 2
    assert landmark_distance(points, 640, 480) is None
    assert landmark_distance([SimpleNamespace(x=0.5, y=0.5)] * 21, 640, 480) is None


def test_missing_model_has_actionable_error_before_opening_camera(tmp_path):
    with pytest.raises(CameraUnavailable, match="prepare-camera"):
        capture(Protocol(), tmp_path / "absent.task")


def test_unavailable_camera_is_released(monkeypatch, tmp_path):
    import cv2

    model = tmp_path / "model.task"
    model.write_bytes(b"not loaded when camera unavailable")
    released = []

    class MissingCamera:
        def isOpened(self):
            return False

        def release(self):
            released.append(True)

    monkeypatch.setattr(cv2, "VideoCapture", lambda _: MissingCamera())
    with pytest.raises(CameraUnavailable, match="camera"):
        capture(Protocol(), model)
    assert released == [True]
