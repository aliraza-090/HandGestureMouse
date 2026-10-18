"""Audio feedback tests using an injected fake winsound backend."""

from handgesturemouse.utils.feedback import DEFAULT_ALIASES, AudioFeedback


class FakeWinsound:
    SND_ASYNC = 1
    SND_ALIAS = 0x10000

    def __init__(self) -> None:
        self.calls = []

    def PlaySound(self, sound, flags):
        self.calls.append((sound, flags))


def test_disabled_plays_nothing():
    backend = FakeWinsound()
    feedback = AudioFeedback(enabled=False, backend=backend)
    feedback.left_click()
    feedback.emergency()
    assert backend.calls == []


def test_enabled_plays_registered_alias_async():
    backend = FakeWinsound()
    feedback = AudioFeedback(enabled=True, backend=backend)
    feedback.left_click()
    assert backend.calls == [(DEFAULT_ALIASES["left_click"], FakeWinsound.SND_ASYNC | FakeWinsound.SND_ALIAS)]


def test_each_event_maps_to_its_alias():
    backend = FakeWinsound()
    feedback = AudioFeedback(enabled=True, backend=backend)
    feedback.left_click()
    feedback.right_click()
    feedback.drag()
    feedback.emergency()
    played = [call[0] for call in backend.calls]
    assert played == [
        DEFAULT_ALIASES["left_click"],
        DEFAULT_ALIASES["right_click"],
        DEFAULT_ALIASES["drag"],
        DEFAULT_ALIASES["emergency"],
    ]


def test_unknown_event_is_noop():
    backend = FakeWinsound()
    feedback = AudioFeedback(enabled=True, backend=backend)
    feedback.play("does-not-exist")
    assert backend.calls == []


def test_set_enabled_toggles():
    backend = FakeWinsound()
    feedback = AudioFeedback(enabled=False, backend=backend)
    feedback.set_enabled(True)
    feedback.drag()
    assert len(backend.calls) == 1
    feedback.set_enabled(False)
    feedback.drag()
    assert len(backend.calls) == 1


def test_backend_errors_never_raise():
    class Exploding:
        SND_ASYNC = 1
        SND_ALIAS = 0x10000

        def PlaySound(self, sound, flags):
            raise RuntimeError("no audio device")

    feedback = AudioFeedback(enabled=True, backend=Exploding())
    feedback.right_click()  # must not raise
