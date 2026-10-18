"""Camera reconnect backoff state-machine tests."""

from handgesturemouse.core.reconnect import ReconnectBackoff


def test_start_activates_and_is_idempotent(fake_clock):
    backoff = ReconnectBackoff(max_attempts=5, interval=2.0, clock=fake_clock)
    assert backoff.active is False
    backoff.start()
    assert backoff.active is True
    assert backoff.attempts == 0
    # A second start must not reset the schedule.
    fake_clock.advance(1)
    backoff.start()
    assert backoff.attempts == 0


def test_not_due_before_interval(fake_clock):
    backoff = ReconnectBackoff(max_attempts=5, interval=2.0, clock=fake_clock)
    backoff.start()
    assert backoff.due() is False
    fake_clock.advance(1.9)
    assert backoff.due() is False
    fake_clock.advance(0.2)
    assert backoff.due() is True


def test_attempts_reschedule_and_exhaust(fake_clock):
    backoff = ReconnectBackoff(max_attempts=3, interval=2.0, clock=fake_clock)
    backoff.start()
    for expected in (1, 2, 3):
        fake_clock.advance(2.0)
        assert backoff.due() is True
        backoff.record_attempt()
        assert backoff.attempts == expected
        assert backoff.due() is False  # rescheduled into the future
    assert backoff.exhausted is True
    fake_clock.advance(10)
    assert backoff.due() is False  # no further attempts


def test_reset_clears_state(fake_clock):
    backoff = ReconnectBackoff(max_attempts=5, interval=2.0, clock=fake_clock)
    backoff.start()
    fake_clock.advance(2.0)
    backoff.record_attempt()
    backoff.reset()
    assert backoff.active is False
    assert backoff.attempts == 0
    assert backoff.due() is False


def test_due_is_false_when_inactive(fake_clock):
    backoff = ReconnectBackoff(clock=fake_clock)
    assert backoff.due() is False
