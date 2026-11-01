import unittest

from server import (
    Engine,
    ManualClock,
    MasterSlotTaken,
    Role,
)


class EngineSkeletonTest(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock(500.0)
        self.engine = Engine(self.clock)

    def test_join_and_leave_sessions(self):
        player = self.engine.join("player-1", Role.PLAYER)
        self.assertEqual(player.role, Role.PLAYER)
        self.assertIn("player-1", self.engine.sessions)
        self.assertIsNone(self.engine.master_sid)

        self.engine.leave("player-1")
        self.assertNotIn("player-1", self.engine.sessions)

    def test_only_one_master(self):
        self.engine.join("master-1", Role.MASTER)
        self.assertEqual(self.engine.master_sid, "master-1")
        with self.assertRaises(MasterSlotTaken):
            self.engine.join("master-2", Role.MASTER)

    def test_leaving_releases_the_master_slot(self):
        self.engine.join("master-1", Role.MASTER)
        self.engine.leave("master-1")
        self.assertIsNone(self.engine.master_sid)
        self.engine.join("master-2", Role.MASTER)
        self.assertEqual(self.engine.master_sid, "master-2")

    def test_snapshot_uses_injected_clock(self):
        snapshot = self.engine.snapshot()
        self.assertEqual(snapshot["server_time"], 500.0)
        self.assertEqual(snapshot["season"], 0)

    def test_id_allocators_are_monotonic(self):
        self.assertEqual(self.engine.allocate_piece_id(), 1)
        self.assertEqual(self.engine.allocate_piece_id(), 2)
        self.assertEqual(self.engine.allocate_furnace_id(), 2)
        self.assertEqual(self.engine.allocate_furnace_id(), 3)
        self.assertEqual(self.engine.allocate_bench_id(), 2)
        self.assertEqual(self.engine.allocate_bench_id(), 3)

    def test_advance_is_a_noop_in_phase_two(self):
        self.assertEqual(self.engine.advance(self.clock.now()), [])


if __name__ == "__main__":
    unittest.main()
