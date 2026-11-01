import unittest

from server import (
    Bench,
    Furnace,
    GameState,
    Piece,
    PieceState,
    Role,
    SAND_CAP,
    WORKERS_TOTAL,
)


class EnumTest(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(Role.MASTER.value, "master")
        self.assertEqual(Role.PLAYER.value, "player")

    def test_piece_states(self):
        self.assertEqual(
            {state.value for state in PieceState},
            {
                "furnace_heating",
                "furnace_ready",
                "bench_working",
                "bench_cooling",
            },
        )


class GameStateDefaultsTest(unittest.TestCase):
    def test_initial_room(self):
        state = GameState()
        self.assertEqual(state.season, 0)
        self.assertFalse(state.season_open)
        self.assertEqual(state.sand, 12)
        self.assertEqual(state.glass, 0)
        self.assertEqual(state.glassblowers_total, WORKERS_TOTAL)
        self.assertEqual(state.glassblowers_busy, 0)
        self.assertEqual(len(state.furnaces), 1)
        self.assertEqual(len(state.benches), 1)
        self.assertEqual(state.pieces, {})

    def test_sand_is_bounded(self):
        with self.assertRaises(ValueError):
            GameState(sand=-1)
        with self.assertRaises(ValueError):
            GameState(sand=SAND_CAP + 1)

    def test_glass_is_non_negative(self):
        with self.assertRaises(ValueError):
            GameState(glass=-1)

    def test_container_counts_are_bounded(self):
        with self.assertRaises(ValueError):
            GameState(furnaces={})
        with self.assertRaises(ValueError):
            GameState(
                furnaces={index: Furnace(index) for index in range(1, 6)}
            )
        with self.assertRaises(ValueError):
            GameState(benches={})

    def test_closed_season_has_no_pieces(self):
        piece = Piece(
            id=1,
            state=PieceState.BENCH_COOLING,
            bench_id=1,
            cooling_started_at=0.0,
            cooling_ends_at=8.0,
        )
        with self.assertRaises(ValueError):
            GameState(
                pieces={1: piece},
                benches={1: Bench(1, piece_id=1, cooling_ends_at=8.0)},
            )

    def test_a_piece_cannot_be_held_twice(self):
        piece = Piece(
            id=1,
            state=PieceState.FURNACE_READY,
            furnace_id=1,
            ready_at=5.0,
        )
        with self.assertRaises(ValueError):
            GameState(
                season_open=True,
                glassblowers_busy=1,
                pieces={1: piece},
                furnaces={
                    1: Furnace(1, piece_id=1),
                    2: Furnace(2, piece_id=1),
                },
                benches={1: Bench(1)},
            )


class SnapshotTest(unittest.TestCase):
    def test_snapshot_matches_contract_shape(self):
        snapshot = GameState().snapshot(now=1234.5)
        self.assertEqual(
            set(snapshot),
            {
                "server_time",
                "season",
                "season_open",
                "sand",
                "glass",
                "glassblowers",
                "furnaces",
                "benches",
                "pieces",
            },
        )
        self.assertEqual(snapshot["server_time"], 1234.5)
        self.assertEqual(
            snapshot["glassblowers"],
            {"total": 8, "busy": 0, "free": 8},
        )
        self.assertEqual(snapshot["furnaces"], [{"id": 1, "piece_id": None}])
        self.assertEqual(
            snapshot["benches"],
            [{"id": 1, "piece_id": None, "cooling_ends_at": None}],
        )
        self.assertEqual(snapshot["pieces"], {})

    def test_snapshot_serializes_active_pieces(self):
        piece = Piece(
            id=1,
            state=PieceState.BENCH_COOLING,
            bench_id=1,
            cooling_started_at=0.0,
            cooling_ends_at=8.0,
        )
        state = GameState(
            season=1,
            season_open=True,
            sand=9,
            glassblowers_busy=0,
            benches={1: Bench(1, piece_id=1, cooling_ends_at=8.0)},
            pieces={1: piece},
        )
        snapshot = state.snapshot(now=8.0)
        self.assertEqual(
            snapshot["benches"],
            [{"id": 1, "piece_id": 1, "cooling_ends_at": 8.0}],
        )
        self.assertEqual(
            snapshot["pieces"]["1"],
            {
                "id": 1,
                "state": "bench_cooling",
                "furnace_id": None,
                "bench_id": 1,
                "ready_at": None,
                "cooling_started_at": 0.0,
                "cooling_ends_at": 8.0,
            },
        )
        self.assertEqual(
            snapshot["glassblowers"], {"total": 8, "busy": 0, "free": 8}
        )


if __name__ == "__main__":
    unittest.main()
