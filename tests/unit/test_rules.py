import unittest

from server import (
    BENCH_SECONDS,
    COOLING_SECONDS,
    HEATING_SECONDS,
    INITIAL_BENCHES,
    INITIAL_FURNACES,
    INITIAL_SAND,
    MAX_BENCHES,
    MAX_FURNACES,
    SAND_CAP,
    SAND_PER_PIECE,
    SAND_REFILL,
    SAND_REFILL_INTERVAL_SECONDS,
    WORKERS_TOTAL,
    crack_chance,
    purchase_cost,
    sand_refill,
)


class RuleConstantsTest(unittest.TestCase):
    def test_documented_constants(self):
        self.assertEqual(INITIAL_SAND, 12)
        self.assertEqual(SAND_CAP, 30)
        self.assertEqual(SAND_PER_PIECE, 3)
        self.assertEqual(SAND_REFILL, 6)
        self.assertEqual(SAND_REFILL_INTERVAL_SECONDS, 10.0)
        self.assertEqual(WORKERS_TOTAL, 8)
        self.assertEqual(INITIAL_FURNACES, 1)
        self.assertEqual(INITIAL_BENCHES, 1)
        self.assertEqual(MAX_FURNACES, 4)
        self.assertEqual(MAX_BENCHES, 4)
        self.assertEqual(HEATING_SECONDS, 5.0)
        self.assertEqual(BENCH_SECONDS, 3.0)
        self.assertEqual(COOLING_SECONDS, 8.0)


class SandRefillTest(unittest.TestCase):
    def test_refill_is_six_below_cap(self):
        self.assertEqual(sand_refill(0), 6)
        self.assertEqual(sand_refill(20), 6)

    def test_refill_is_clamped_at_cap(self):
        self.assertEqual(sand_refill(26), 4)
        self.assertEqual(sand_refill(30), 0)


class PurchaseCostTest(unittest.TestCase):
    def test_cost_uses_current_count_and_season(self):
        self.assertEqual(purchase_cost(1, 1), 3)
        self.assertEqual(purchase_cost(2, 1), 5)
        self.assertEqual(purchase_cost(3, 1), 7)
        self.assertEqual(purchase_cost(1, 2), 5)


class CrackChanceTest(unittest.TestCase):
    def test_immediate_take_is_certain_to_crack(self):
        self.assertEqual(crack_chance(0.0), 100.0)

    def test_halfway_is_fifty_percent(self):
        self.assertEqual(crack_chance(4.0), 50.0)

    def test_fully_cooled_is_safe(self):
        self.assertEqual(crack_chance(8.0), 0.0)
        self.assertEqual(crack_chance(12.0), 0.0)


if __name__ == "__main__":
    unittest.main()
