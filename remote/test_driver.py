import pytest

import driver as driver_module
from driver import RobotDriver


class FakeClock:
    """Stands in for time.monotonic so tests can move time forward instantly."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeCrawler:
    """Records every call instead of moving servos.

    Stops the driver after `stop_after` do_action calls, so run() can be
    called directly on the test's own thread and still finish.
    """

    def __init__(self, driver=None, stop_after=None, fail_on=None):
        self.driver = driver
        self.stop_after = stop_after
        self.fail_on = fail_on
        self.calls = []

    def do_action(self, name, step, speed):
        if name == self.fail_on:
            raise RuntimeError(f"servo error during {name}")
        self.calls.append(("do_action", name, step, speed))
        if self.stop_after is not None and len(self.calls) >= self.stop_after:
            self.driver.stop_event.set()

    def do_step(self, name, speed):
        self.calls.append(("do_step", name, speed))


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(driver_module.time, "monotonic", fake)
    return fake


@pytest.fixture
def d(clock):
    return RobotDriver(None)


# --- _choose_move: direction ---

@pytest.mark.parametrize("x, y, gait", [
    (0.0, 1.0, "forward"),
    (0.0, -1.0, "backward"),
    (-1.0, 0.0, "turn left"),
    (1.0, 0.0, "turn right"),
])
def test_full_push_picks_gait_at_max_speed(d, x, y, gait):
    d.drive(x, y)
    assert d._choose_move() == (gait, RobotDriver.SPEED_MAX)


def test_stronger_axis_wins(d):
    d.drive(0.3, 0.9)
    assert d._choose_move()[0] == "forward"
    d.drive(-0.9, 0.3)
    assert d._choose_move()[0] == "turn left"


def test_equal_axes_prefer_walking_over_turning(d):
    d.drive(0.7, 0.7)
    assert d._choose_move()[0] == "forward"


# --- _choose_move: deadzone and speed ---

def test_inside_deadzone_stands_still(d):
    d.drive(0.1, -0.2)
    assert d._choose_move() is None


def test_deadzone_edge_is_min_speed(d):
    d.drive(0.0, RobotDriver.DEADZONE)
    assert d._choose_move() == ("forward", RobotDriver.SPEED_MIN)


def test_speed_scales_with_push(d):
    d.drive(-0.5, 0.1)
    assert d._choose_move() == ("turn left", 63)


# --- drive: clamping ---

def test_out_of_range_input_is_clamped(d):
    d.drive(0.0, 5.0)
    assert d._choose_move() == ("forward", RobotDriver.SPEED_MAX)
    d.drive(-12.0, 0.0)
    assert d._choose_move() == ("turn left", RobotDriver.SPEED_MAX)


# --- _choose_move: safety cutoff ---

def test_no_input_yet_stands_still(d):
    assert d._choose_move() is None


def test_fresh_input_is_used(d, clock):
    d.drive(0.0, 1.0)
    clock.now += RobotDriver.TIMEOUT - 0.01
    assert d._choose_move() is not None


def test_stale_input_stops_the_robot(d, clock):
    d.drive(0.0, 1.0)
    clock.now += RobotDriver.TIMEOUT + 0.01
    assert d._choose_move() is None


def test_new_input_after_timeout_resumes(d, clock):
    d.drive(0.0, 1.0)
    clock.now += 10
    d.drive(0.0, 1.0)
    assert d._choose_move() is not None


# --- run ---

def test_queued_actions_run_before_walking(clock):
    d = RobotDriver(None)
    d.crawler = FakeCrawler(driver=d, stop_after=3)
    d.drive(0.0, 1.0)
    d.action("wave")
    d.action("dance")

    d.run()

    assert d.crawler.calls[:3] == [
        ("do_action", "wave", 1, RobotDriver.ACTION_SPEED),
        ("do_action", "dance", 1, RobotDriver.ACTION_SPEED),
        ("do_action", "forward", 1, RobotDriver.SPEED_MAX),
    ]


def test_sits_when_stopped(clock):
    d = RobotDriver(None)
    d.crawler = FakeCrawler(driver=d, stop_after=1)
    d.drive(0.0, 1.0)

    d.run()

    assert d.crawler.calls[-1] == ("do_step", "sit", 40)


def test_sits_even_if_an_action_crashes(clock):
    d = RobotDriver(None)
    d.crawler = FakeCrawler(driver=d, fail_on="wave")
    d.action("wave")

    with pytest.raises(RuntimeError):
        d.run()

    assert d.crawler.calls == [("do_step", "sit", 40)]


def test_start_and_stop_with_real_thread():
    d = RobotDriver(None)
    d.crawler = FakeCrawler(driver=d)
    d.start()
    d.stop()

    assert not d.thread.is_alive()
    assert d.crawler.calls == [("do_step", "sit", 40)]
