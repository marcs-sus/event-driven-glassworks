# event-driven-glassworks

Cooperative real-time glassworks. Two roles share a global room: the **Master**
opens and closes seasons; **Players** produce glass through furnaces and
benches. The server is the single source of truth; the client only emits
requests and reacts to facts.

## Stack

- Python 3.11+ / python-socketio / uvicorn — see `requirements.txt`
- Vue 3 + Phaser 3 + Socket.IO client — all loaded via CDN, no build step, no bundler

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload
```

Open http://localhost:8000 in **two tabs** (a third tab is useful to test the
Master slot).

**Note:** the village state lives in process memory. `uvicorn --reload`
restarts the server on save and resets the game. Reload the tabs after saving.

## Events

See `specs/001-glassworks/spec.md` for the full catalog, rejection reasons, and test cases
T1–T9.

Validation order and rejection reasons follow
`specs/001-glassworks/data-model.md` (section _Validation Rules by Request_).

## AI usage

This project was developed with AI assistance:

- **GitHub Spec Kit** (`specify-cli`) for spec-driven planning —
  `/speckit.constitution`, `/speckit.plan`, `/speckit.tasks`,
  `/speckit.implement`.
- **opencode** with the **DeepSeek V4.1 Flash Free** model for
  implementation prompts.

Every AI-generated change was reviewed, run locally with `uvicorn
server:app --reload`, and verified manually in two browser tabs before commit.
The specification (`specs/001-glassworks/spec.md`) was written first, and each phase is a
separate commit.
