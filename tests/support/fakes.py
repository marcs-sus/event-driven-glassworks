"""Small test doubles: a recording broadcaster and a seeded RNG."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecordingBroadcaster:
    """Collect facts instead of sending them over a socket."""

    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        self.events.append((event, payload))

    def clear(self) -> None:
        self.events.clear()


def seeded_rng(seed: int = 1234) -> random.Random:
    return random.Random(seed)
