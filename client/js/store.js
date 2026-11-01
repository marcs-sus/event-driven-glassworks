/*
 * Server-state mirror and request helpers.
 *
 * The client never computes authoritative state.  It stores the latest
 * complete snapshot and exposes one helper per documented client request.
 */
(function (global) {
  "use strict";

  const { reactive } = global.Vue;

  const state = reactive({
    snapshot: null,
    role: null,
    connected: false,
    lastError: null,
    lastCause: null,
    serverOffset: 0,
    events: [],
    nextEventId: 1,
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
      cause:
        data.causa || data.cause || (direction === "up" ? "client" : "—"),
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

  // Phase 2 request helpers.  The server registers these handlers in later
  // phases; keeping them here satisfies the single client request surface.
  function openSeason() {
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

  function takeGlass(benchId) {
    emitRequest("glass.take_requested", { bench_id: benchId });
  }

  function buyFurnace() {
    emitRequest("furnace.purchase_requested", {});
  }

  function buyBench() {
    emitRequest("bench.purchase_requested", {});
  }

  global.GlassworksStore = {
    state,
    applySnapshot,
    logEvent,
    clearEvents,
    openSeason,
    closeSeason,
    requestPiece,
    moveToBench,
    takeGlass,
    buyFurnace,
    buyBench,
  };
})(window);
