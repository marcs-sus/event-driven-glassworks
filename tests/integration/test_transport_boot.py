import json
import unittest

from server import ManualClock, create_app
from tests.support.transport import TransportHarness, http_request


class TransportBootTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.clock = ManualClock(1_767_225_600.0)
        self.application = create_app(clock=self.clock)
        self.harness = TransportHarness(self.application)
        await self.harness.start()

    async def asyncTearDown(self) -> None:
        await self.harness.stop()
        self.assertIsNone(self.application.game.ticker_task)
        self.assertEqual(self.application.game.pending_tasks, frozenset())

    async def test_ticker_is_running_after_startup(self):
        task = self.application.game.ticker_task
        self.assertIsNotNone(task)
        self.assertFalse(task.done())

    async def test_phase_three_registers_gameplay_handlers(self):
        self.assertEqual(
            set(self.application.game.sio.handlers["/"]),
            {
                "connect",
                "disconnect",
                "glassworks.start_requested",
                "glassworks.close_requested",
                "glassmaking.requested",
                "glassmaking.bench_requested",
                "glass.take_requested",
            },
        )

    async def test_cors_allows_any_origin(self):
        self.assertEqual(
            self.application.game.sio.eio.cors_allowed_origins, "*"
        )

    async def test_master_connects_and_receives_state_synced(self):
        client = await self.harness.connect("master")
        payload = await client.wait_for("state.synced")

        self.assertEqual(payload["causa"], "connection")
        state = payload["state"]
        self.assertEqual(state["season"], 0)
        self.assertFalse(state["season_open"])
        self.assertEqual(state["sand"], 12)
        self.assertEqual(state["glass"], 0)
        self.assertEqual(
            state["glassblowers"], {"total": 8, "busy": 0, "free": 8}
        )
        self.assertEqual(
            state["furnaces"], [{"id": 1, "piece_id": None}]
        )
        self.assertEqual(
            state["benches"],
            [{"id": 1, "piece_id": None, "cooling_ends_at": None}],
        )
        self.assertEqual(state["pieces"], {})
        self.assertEqual(state["server_time"], self.clock.now())
        self.assertEqual(
            self.application.game.engine.master_sid, client.socket_sid
        )

    async def test_player_connects_and_receives_state_synced(self):
        client = await self.harness.connect("player")
        payload = await client.wait_for("state.synced")
        self.assertEqual(payload["causa"], "connection")
        self.assertEqual(payload["state"]["season"], 0)
        self.assertIsNone(self.application.game.engine.master_sid)

    async def test_invalid_role_is_rejected_then_disconnected(self):
        client = await self.harness.connect("wizard")
        payload = await client.wait_for("operation.rejected")
        self.assertEqual(payload["causa"], "connection")
        self.assertEqual(payload["reason"], "invalid role")
        self.assertNotIn(
            client.socket_sid, self.application.game.engine.sessions
        )

    async def test_second_master_is_rejected(self):
        first = await self.harness.connect("master")
        await first.wait_for("state.synced")

        second = await self.harness.connect("master")
        payload = await second.wait_for("operation.rejected")
        self.assertEqual(payload["causa"], "connection")
        self.assertEqual(payload["reason"], "a master already exists")
        self.assertEqual(
            self.application.game.engine.master_sid, first.socket_sid
        )

    async def test_static_client_and_asset_mime_types(self):
        status, headers, body = await http_request(
            "127.0.0.1", self.harness.port, "GET", "/"
        )
        self.assertEqual(status, 200)
        self.assertTrue(
            headers["content-type"].startswith("text/html")
        )
        self.assertIn(b'id="app"', body)

        status, headers, body = await http_request(
            "127.0.0.1", self.harness.port, "GET", "/js/main.js"
        )
        self.assertEqual(status, 200)
        self.assertTrue(
            headers["content-type"].startswith("text/javascript")
        )

        status, headers, body = await http_request(
            "127.0.0.1",
            self.harness.port,
            "GET",
            "/assets/tileset-vila.png",
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "image/png")
        self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))

        status, headers, body = await http_request(
            "127.0.0.1", self.harness.port, "GET", "/assets/vila.json"
        )
        self.assertEqual(status, 200)
        self.assertTrue(
            headers["content-type"].startswith("application/json")
        )
        map_data = json.loads(body)
        self.assertIn("layers", map_data)
        self.assertIn("tilesets", map_data)

    async def test_missing_asset_is_not_index_fallback(self):
        status, headers, _ = await http_request(
            "127.0.0.1",
            self.harness.port,
            "GET",
            "/assets/does-not-exist.png",
        )
        self.assertEqual(status, 404)
        self.assertTrue(
            headers["content-type"].startswith("text/plain")
        )

    async def test_path_traversal_is_rejected(self):
        status, _, _ = await http_request(
            "127.0.0.1",
            self.harness.port,
            "GET",
            "/assets/%2e%2e/server.py",
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
