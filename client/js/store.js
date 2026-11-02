/*
 * Server-state mirror and request helpers.
 *
 * The client never computes authoritative state.  It stores the latest
 * complete snapshot and exposes one helper per documented client request.
 */
(function (global) {
  "use strict";

  const { reactive } = global.Vue;

  const MAX_EQUIPMENT = 4;

  // Mirror of the server's purchase formula: count * season * 2 + 1.
  function purchaseCost(count, season) {
    return count * season * 2 + 1;
  }

  const state = reactive({
    snapshot: null,
    role: null,
    connected: false,
    lastError: null,
    lastCause: null,
    notice: "",
    serverOffset: 0,
    events: [],
    nextEventId: 1,
    get currentFurnaces() {
      return this.snapshot && Array.isArray(this.snapshot.furnaces)
        ? this.snapshot.furnaces.length
        : 0;
    },
    get currentBenches() {
      return this.snapshot && Array.isArray(this.snapshot.benches)
        ? this.snapshot.benches.length
        : 0;
    },
    get currentSeason() {
      return this.snapshot && typeof this.snapshot.season === "number"
        ? this.snapshot.season
        : 0;
    },
    get furnaceCost() {
      return purchaseCost(this.currentFurnaces, this.currentSeason);
    },
    get benchCost() {
      return purchaseCost(this.currentBenches, this.currentSeason);
    },
    get canAffordFurnace() {
      return (
        !!this.snapshot &&
        this.currentFurnaces < MAX_EQUIPMENT &&
        this.snapshot.glass >= this.furnaceCost
      );
    },
    get canAffordBench() {
      return (
        !!this.snapshot &&
        this.currentBenches < MAX_EQUIPMENT &&
        this.snapshot.glass >= this.benchCost
      );
    },
  });

  function applySnapshot(snapshot, cause) {
    state.snapshot = snapshot || null;
    if (snapshot && typeof snapshot.server_time === "number") {
      // Browser clock minus server clock; display-only countdowns use it.
      state.serverOffset = Date.now() / 1000 - snapshot.server_time;
    }
    if (cause) {
      state.lastCause = cause;
    }
  }

  function logEvent(direction, name, payload, reaction) {
    const data = payload == null ? {} : payload;
    state.events.unshift({
      id: state.nextEventId++,
      direction,
      timestamp: new Date().toLocaleTimeString(),
      name,
      cause: data.causa || data.cause || (direction === "up" ? "client" : "—"),
      payload: JSON.stringify(data),
      reaction: reaction || "",
    });
    if (state.events.length > 200) {
      state.events.length = 200;
    }
  }

  function clearEvents() {
    state.events.splice(0, state.events.length);
  }

  function emitRequest(name, payload) {
    if (!global.GlassworksSocket) {
      throw new Error("Socket.IO client is not ready");
    }
    global.GlassworksSocket.emitRequest(name, payload);
  }

  // Phase 3 request helpers.  Each one goes through emitRequest so the event
  // panel records the ⬆ emit row before the socket write.
  function startSeason() {
    emitRequest("glassworks.start_requested", {});
  }

  function closeSeason() {
    emitRequest("glassworks.close_requested", {});
  }

  function requestPiece(furnaceId) {
    emitRequest("glassmaking.requested", { furnace_id: furnaceId });
  }

  function moveToBench(furnaceId) {
    emitRequest("glassmaking.bench_requested", { furnace_id: furnaceId });
  }

  function takePiece(benchId) {
    emitRequest("glass.take_requested", { bench_id: benchId });
  }

  // Phase 5 purchase helpers.  Costs are display-only mirrors of the server
  // rule; the engine remains authoritative.
  function purchaseFurnace() {
    emitRequest("furnace.purchase_requested", {});
  }

  function purchaseBench() {
    emitRequest("bench.purchase_requested", {});
  }

  // Phase 2 names kept as aliases so older call sites keep working.
  const openSeason = startSeason;
  const takeGlass = takePiece;
  const buyFurnace = purchaseFurnace;
  const buyBench = purchaseBench;

  global.GlassworksStore = {
    state,
    purchaseCost,
    applySnapshot,
    logEvent,
    clearEvents,
    startSeason,
    closeSeason,
    requestPiece,
    moveToBench,
    takePiece,
    openSeason,
    takeGlass,
    purchaseFurnace,
    purchaseBench,
    buyFurnace,
    buyBench,
  };
})(window);
