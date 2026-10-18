"""Camera lifecycle tests using an injected fake capture backend."""

import pytest

from handgesturemouse.camera.camera_manager import CameraError, CameraManager


class FakeCap:
    def __init__(self, index=0, opened=True, frames=None, raise_read=False):
        self.index = index
        self._opened = opened
        self._frames = list(frames or [])
        self._released = False
        self.raise_read = raise_read
        self.set_calls = []

    def isOpened(self):
        return self._opened and not self._released

    def read(self):
        if self.raise_read:
            raise RuntimeError("device error")
        if self._frames:
            return True, self._frames.pop(0)
        return False, None

    def set(self, prop, value):
        self.set_calls.append((prop, value))

    def release(self):
        self._released = True


def test_list_cameras_returns_open_indices_and_releases_all():
    created = {}

    def backend(index):
        cap = FakeCap(index=index, opened=(index in (0, 2)))
        created[index] = cap
        return cap

    manager = CameraManager(backend=backend, scan_limit=4)
    assert manager.list_cameras() == [0, 2]
    assert all(cap._released for cap in created.values())


def test_open_unavailable_camera_raises_camera_error():
    manager = CameraManager(backend=lambda i: FakeCap(opened=False))
    with pytest.raises(CameraError):
        manager.open(0)


def test_open_after_backend_failure_raises_camera_error():
    def backend(index):
        raise RuntimeError("no camera subsystem")

    manager = CameraManager(backend=backend)
    with pytest.raises(CameraError):
        manager.open(0)


def test_read_returns_none_when_camera_not_open():
    manager = CameraManager(backend=lambda i: FakeCap())
    assert manager.read() is None
    assert manager.is_open() is False


def test_open_read_release_lifecycle():
    cap = FakeCap(opened=True, frames=["frame-a"])
    manager = CameraManager(backend=lambda i: cap)
    manager.open(0)
    assert manager.is_open() is True
    manager.set_open_dimensions(640, 480)
    assert cap.set_calls == [(3, 640), (4, 480)]
    assert manager.read() == "frame-a"
    manager.release()
    assert manager.is_open() is False
    assert manager.read() is None
    assert cap._released is True


def test_read_failure_returns_none_without_raising():
    cap = FakeCap(opened=True, raise_read=True)
    manager = CameraManager(backend=lambda i: cap)
    manager.open(0)
    assert manager.read() is None
