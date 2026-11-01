import unittest

from server import (
    Cause,
    Event,
    FACT_EVENTS,
    REQUEST_EVENTS,
    Rejection,
)


class EventRegistryTest(unittest.TestCase):
    def test_every_request_ends_in_requested(self):
        for name in REQUEST_EVENTS:
            self.assertTrue(
                name.endswith("requested"),
                f"{name} must end in requested",
            )

    def test_every_fact_uses_a_past_tense_action(self):
        for name in FACT_EVENTS:
            action = name.split(".", 1)[1]
            self.assertTrue(
                action.endswith(("ed", "ted", "ped")),
                f"{name} must use a past-tense action",
            )

    def test_unicast_events_are_named(self):
        self.assertEqual(Event.STATE_SYNCED.value, "state.synced")
        self.assertEqual(
            Event.OPERATION_REJECTED.value, "operation.rejected"
        )

    def test_all_cause_values_exist(self):
        self.assertEqual(
            {item.value for item in Cause},
            {
                "master",
                "player",
                "timer",
                "sand_tick",
                "master_disconnected",
                "connection",
            },
        )

    def test_all_rejection_reasons_exist(self):
        self.assertEqual(
            {item.value for item in Rejection},
            {
                "season not open",
                "season already open",
                "not enough sand",
                "not enough glass",
                "no free worker",
                "furnace busy",
                "bench busy",
                "piece not ready",
                "max furnaces reached",
                "max benches reached",
                "only master can open season",
                "only master can close season",
                "only players can interact",
                "a master already exists",
                "invalid role",
                "unknown furnace",
                "unknown bench",
                "malformed payload",
                "no piece to take",
            },
        )


if __name__ == "__main__":
    unittest.main()
