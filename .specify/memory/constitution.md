<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR. Materially expanded guidance: explicit client behavior
(request/fact separation), exact event naming patterns, mandatory event test
coverage, a closed dependency stack, and one-commit-per-stage delivery. No
principle was removed or redefined incompatibly.

Modified principles:
- I. Server-Authoritative Event Flow (NON-NEGOTIABLE) — clients react to facts
- III. Event Contract Discipline — explicit object.action_past and
  object.action_requested naming, event test-scenario requirement
- IV. Test-First, Time-Controlled Verification (NON-NEGOTIABLE) — every event
  covered by a spec scenario and automated test
- V. Minimal In-Memory Architecture — closed server and client dependency stack

Added sections: none
Removed sections: none

Deferred TODOs: none
-->

# Glassworks Constitution

## Core Principles

### I. Server-Authoritative Event Flow (NON-NEGOTIABLE)

The server is the single source of truth for all shared state: season, sand,
glass, glassblowers, furnaces, benches, and piece lifecycle. Clients MUST only
emit request events and react to broadcast facts; they MUST NOT compute
authoritative outcomes, mutate shared state locally, or treat local predictions
as truth. Every server event that changes state MUST broadcast the resulting
`state` and a `causa`. Failed requests MUST be answered to the requester only,
via `operation.rejected` with a reason defined in `docs/spec.md`. Validation and
mutation for a request MUST be atomic with respect to concurrent requests, so
that simultaneous intents resolve to exactly one success and one documented
rejection.

Rationale: multiple players share one global sand stock, worker pool, and
glass storage. Without server authority and atomic validation, clients and
interleaved handlers can diverge or duplicate state changes (see scenario T3).

### II. Single Source of Game Rules

All game constants, costs, caps, timings, and formulas MUST be defined exactly
once in a dedicated rules module or configuration, and referenced everywhere
else. This includes initial sand, sand cap, sand per piece, refill amount and
interval, worker count, furnace/bench/cooling durations, furnace and bench
caps, purchase cost, and crack chance. Rule logic SHOULD be expressed as pure
functions that can be evaluated without transport or timers. No handler,
timer, or component may re-declare a rule literal. Any rule change MUST update
`docs/spec.md` in the same change.

Rationale: duplicated constants silently drift. A single rules source keeps
server behavior, tests, and the published specification aligned.

### III. Event Contract Discipline

Every event MUST be documented in `docs/spec.md` with its direction, payload,
and effect before it is implemented. Event names MUST follow the
`object.action_past` pattern for server facts, with a past-tense action
(`glassmaking.started`, `glass.stored`, `operation.rejected`), and the
`object.action_requested` pattern for client requests, ending in `requested`
(`glassmaking.requested`, `glass.take_requested`,
`furnace.purchase_requested`).
Payloads MUST be validated server-side before use; malformed payloads, unknown
identifiers, and invalid roles MUST produce an `operation.rejected` event with a
documented reason rather than an unhandled exception. Every event in the
contract MUST have at least one test scenario in the Test Cases section of
`docs/spec.md`; an event without a scenario is not part of the contract.
Adding, renaming, or removing an event is a contract change and MUST be
reflected in the specification and its tests within the same change.

Rationale: the event table is the only shared contract between the server and
every client. Undocumented or drifting events make clients silently incorrect,
and untested events permit contract violations to ship unnoticed.

### IV. Test-First, Time-Controlled Verification (NON-NEGOTIABLE)

Tests MUST be written and observed failing before the behavior they cover is
implemented. The acceptance scenarios T1 through T7 in `docs/spec.md` MUST be
automated, and the full suite MUST pass before a change is merged. Every event
MUST be exercised by at least one automated test scenario, and that scenario
MUST be documented in the Test Cases section of `docs/spec.md`. Every documented
rejection reason MUST have a test. Time-dependent behavior MUST be verified
through an injectable clock or timer abstraction; tests MUST NOT depend on real
sleeps. Randomness, including crack chance, MUST be injectable or
deterministically seeded so outcomes are reproducible.

Rationale: timers, races, and probability are the highest-risk parts of this
domain. Without deterministic time and randomness, the specification cannot be
verified and regressions become invisible.

### V. Minimal In-Memory Architecture

The system MUST remain a single Python process exposing Socket.IO events over
an ASGI server, with all game state held in memory. Transport handlers MUST be
separated from domain logic, and domain code MUST NOT import the socket
library. The runtime stack is closed: Python 3 with `python-socketio` and
`uvicorn` on the server, and Vue 3 with Phaser 3 loaded via CDN on the client.
No database, message broker, cache, or other external service may be added.
Any additional dependency, bundled client build step, or npm package requires an
amendment to this principle. Loss of state on restart is accepted for the
current scope and MUST be stated in the specification.

Rationale: the game has one shared room and modest load. A closed, minimal
stack keeps the event model auditable and prevents infrastructure that the
current requirements do not justify.

## Technical Constraints

- **Server stack**: Python 3 with `python-socketio` and `uvicorn` as declared in
  `requirements.txt`; the application MUST start as a single ASGI entry point.
- **Client stack**: Vue 3 and Phaser 3 loaded via CDN, with no bundler, npm
  dependency tree, or build step.
- **Transport**: Socket.IO events are the only client/server interface. Adding
  another protocol requires a specification amendment.
- **State lifetime**: All state is process-local and non-persistent. A restart
  clears season progress; this limitation MUST be documented.
- **Time**: All durations use a single injectable clock. Timers MUST be
  cancellable, and closing a season MUST cancel or invalidate outstanding
  timers so no stale event is emitted.
- **Roles**: Exactly one Master may exist at a time. The server MUST enforce
  role permissions; the Master slot MUST be released on disconnect, and an open
  season MUST close with causa `master_disconnected`.
- **Trust boundary**: All client payloads are untrusted. Role, resource
  availability, and state transitions MUST be validated server-side on every
  request.
- **Consistency**: Broadcasts MUST carry the complete current `state` so a
  client can render without replaying history.

## Development Workflow

- **Specification first**: `docs/spec.md` is the authoritative behavior
  specification. Behavior changes MUST update it before or together with code.
- **Test gate**: The full automated suite MUST pass, including T1 through T7,
  every rejection reason, and at least one scenario per event, before merge.
- **Review checklist**: Reviewers MUST verify server authority, request/fact
  separation, event naming and scenario coverage, centralized rules,
  deterministic tests, and the closed dependency stack.
- **Definition of done**: A change is complete only when code, tests, and
  specification updates are present, every event has a documented scenario, and
  no request path can fail silently.
- **Staged commits**: Deliver exactly one commit per implementation stage. A
  stage is one coherent, independently reviewable unit from the implementation
  plan; unrelated stages MUST NOT be combined, and a single stage MUST NOT be
  fragmented across commits. Use conventional commit prefixes (`feat:`, `fix:`,
  `docs:`, `test:`, `refactor:`, `chore:`).
- **Complexity justification**: Any deviation from Principle V, or any new
  abstraction, MUST be justified in the change description with the concrete
  requirement it serves.

## Governance

This constitution supersedes conflicting local practices. `docs/spec.md`
provides runtime and behavioral guidance and MUST remain consistent with these
principles.

Amendments MUST be proposed as a change to this file that states the rationale,
the affected principles, and any migration required for existing code or
clients. Amendments take effect when approved by a project maintainer and
merged. The Sync Impact Report produced during an amendment is review material
and MUST be removed before the amended constitution is committed.

Versioning follows semantic versioning. MAJOR increments cover backward
incompatible governance changes such as removing or redefining a principle.
MINOR increments cover new principles or sections, or materially expanded
guidance. PATCH increments cover clarifications, wording fixes, and other
non-semantic refinements. The ratification date records initial adoption and
does not change on amendment; the last-amended date MUST be updated for every
accepted change.

Every pull request and review MUST verify compliance with this constitution.
Non-compliant work MUST NOT be merged. Any temporary exception MUST be recorded
in the change description with an owner and an expiration, and MUST be resolved
before the next minor release.

**Version**: 1.1.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-01
