# Glassworks — LPP Trabalho 01

Cooperative real-time glassworks game. Two roles: Master opens and closes
seasons; players produce glass through furnaces and benches. Server is the
single source of truth; the client only emits requests and reacts to facts.

## Team

- Your Name — [@your-handle](https://github.com/your-handle)

## Stack

- Python 3.11+ / python-socketio / uvicorn
- Vue 3 + Phaser 3 + Socket.IO client (all via CDN, no build step)

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload
```

Open http://localhost:8000 in two tabs:

Tab A → "Join as Master"
Tab B → "Join as Player"

## Testing

Both tabs should show the same state after connecting.

A third tab trying "Join as Master" is rejected with "a master already exists".

Close the Master tab; reload the third tab → it can now become Master.

## Events

See docs/spec.md for the full event catalog and test cases T1–T9.

## AI usage

This project was developed with the assistance of:

GitHub Spec Kit for spec-driven planning (/speckit.\* commands)

`opencode` with the DeepSeek V4.1 Flash Free model for implementation

All code was reviewed and validated manually by the developer.
