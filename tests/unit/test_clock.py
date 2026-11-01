import time
import unittest

from server import ManualClock, SystemClock, DEFAULT_EPOCH


class SystemClockTest(unittest.TestCase):
    def test_now_returns_epoch_seconds(self):
        before = time.time()
        value = SystemClock().now()
        after = time.time()
        self.assertIsInstance(value, float)
        self.assertGreaterEqual(value, before)
        self.assertLessEqual(value, after)


class ManualClockTest(unittest.TestCase):
    def test_default_epoch_is_stable(self):
        clock = ManualClock()
        self.assertEqual(clock.now(), DEFAULT_EPOCH)

    def test_advance_moves_time_forward(self):
        clock = ManualClock(1000.0)
        self.assertEqual(clock.now(), 1000.0)
        self.assertEqual(clock.advance(5.5), 1005.5)
        self.assertEqual(clock.now(), 1005.5)

    def test_set_overrides_time(self):
        clock = ManualClock(1000.0)
        clock.set(42.0)
        self.assertEqual(clock.now(), 42.0)


if __name__ == "__main__":
    unittest.main()
