# Glassworks — LPP Trabalho 01

Cooperative real-time glassworks. Two roles share a global room: the **Master**
opens and closes seasons; **Players** produce glass through furnaces and
benches. The server is the single source of truth; the client only emits
requests and reacts to facts.

## Team

- Marcos Vinicius Cunha — [@marcs-sus](https://github.com/marcs-sus)

## Stack

- Python 3.11+ / python-socketio / uvicorn — see `requirements.txt`
- Vue 3 + Phaser 3 + Socket.IO client — all loaded via CDN, no build step, no bundler

## Run

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
uvicorn server:app --reload
```

Open http://localhost:8000 in **two tabs** (a third tab is useful to test the
Master slot).

**Note:** the village state lives in process memory. `uvicorn --reload`
restarts the server on save and resets the game. Reload the tabs after saving.

## How to test with two tabs

1. **Tab A** → **Join as Master**. HUD shows Season 0, Sand 12, Glass 0,
   Workers 0/8, Furnaces 1/4, Benches 1/4. Event panel shows `⬇ on
state.synced` (causa `connection`).
2. **Tab B** → **Join as Player**. Same state; independent event panel.
3. **Tab C** → **Join as Master** → rejected with `a master already exists` and
   **no** `state.synced`.
4. Tab A clicks **Open season** → both tabs show `⬇ on glassworks.started`
   (causa `master`). Season becomes 1, and the "Next sand" countdown starts at
   10s.
5. Every 10s, both tabs receive `⬇ on sand.stored` (causa `sand_tick`). At the
   cap (30/30) it still emits with `gained: 0`.
6. Tab B clicks furnace 1 → `glassmaking.started` (sand −3, worker busy). After
   5s → `glassmaking.heated` (causa `timer`). Click again →
   `glassmaking.bench_started`. After 3s → `glassmaking.completed` (cooling
   starts, worker freed). After 8s, click the bench → `glass.stored`. Click it
   earlier to test `glass.cracked`.
7. With 3+ glass, Tab B clicks **Buy furnace** → `furnace.purchased`
   (cost = `count * season * 2 + 1`). The 2nd furnace costs 3, the 3rd costs 5,
   the 4th costs 7 (season 1). At 4/4, the next attempt rejects with
   `max furnaces reached`.
8. Tab A clicks **Close season** → `glassworks.closed` (causa `master`). Sand
   and glass are **not** reset yet; they reset on the next `glassworks.started`.
   Furnaces and benches persist across seasons.
9. **Close Tab A** while the season is open → Tab B receives `glassworks.closed`
   (causa `master_disconnected`), in-progress pieces are removed, workers are
   freed, stored glass is kept. Reload Tab A, pick Master — the slot is free.
10. **Malformed payload** (F12 console on Tab B):
    `socket.emit("glassmaking.requested", {})` → `operation.rejected` with
    reason `malformed payload`. With `{ furnace_id: 99 }` → `unknown furnace`.
    With `{ furnace_id: "1" }` → `malformed payload` (string, not int).

## Events

See `docs/spec.md` for the full catalog, rejection reasons, and test cases
T1–T9. Two copies are kept byte-identical: `docs/spec.md` (authoritative) and
`specs/001-glassworks/spec.md` (Spec Kit working copy).

Validation order and rejection reasons follow
`specs/001-glassworks/data-model.md` (section _Validation Rules by Request_).

## Answers to the required questions

### 1. Which events does the system emit and listen to?

Server facts (clients listen):
`state.synced`, `glassworks.started`, `glassworks.closed`,
`glassmaking.started`, `glassmaking.heated`, `glassmaking.bench_started`,
`glassmaking.completed`, `glass.stored`, `glass.cracked`, `sand.stored`,
`furnace.purchased`, `bench.purchased`, `operation.rejected`.

Client requests (server listens):
`glassworks.start_requested`, `glassworks.close_requested`,
`glassmaking.requested`, `glassmaking.bench_requested`,
`glass.take_requested`, `furnace.purchase_requested`,
`bench.purchase_requested`.

### 2. How does the system know when to update the other players?

Every mutation happens inside a Socket.IO handler under a single
`asyncio.Lock`; after mutating, the handler calls `self.broadcast(...)`, which
sends the resulting _fact_ (event name + snapshot + `causa` + extras) to every
connected socket. Timers are driven by a 50 ms tick loop
(`Glassworks._tick_loop`) that calls `Engine.advance(now)` and broadcasts any
facts produced. Clients never poll: they only react to `socket.on(...)`.

### 3. Which part of the code clearly shows the event-driven paradigm?

- **Server:** `server.py` → `Glassworks._handle_connect` and the
  `_handle_*` request handlers; `Engine.advance` is the timer event source.
- **Client:** `client/js/main.js` → every `socket.listen(...)` is a handler
  with an explicit **reaction**; `client/js/store.js` → `startSeason`,
  `closeSeason`, `requestPiece`, `moveToBench`, `takePiece`,
  `purchaseFurnace`, `purchaseBench` emit requests.
- **Visible in the UI:** the **event panel** renders, in real time, every
  `⬆ emit` / `⬇ on` with the event name, timestamp, **causa**, payload, and
  the reaction string — making the emit/on/cause/reaction chain observable.

## AI usage

This project was developed with AI assistance:

- **GitHub Spec Kit** (`specify-cli`) for spec-driven planning —
  `/speckit.constitution`, `/speckit.plan`, `/speckit.tasks`,
  `/speckit.implement`.
- **opencode** with the **DeepSeek V4.1 Flash Free** model for
  implementation prompts.

Every AI-generated change was reviewed, run locally with `uvicorn
server:app --reload`, and verified manually in two browser tabs before commit.
The specification (`docs/spec.md`) was written first, and each phase is a
separate commit.

## Repository

- **Name:** `lpp-trabalho01-marcos`
- **Visibility:** public
- **Course:** Linguagem de Programação e Paradigmas — Sistemas de Informação —
  2026/2
