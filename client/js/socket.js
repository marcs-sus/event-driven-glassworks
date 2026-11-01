/*
 * Socket.IO singleton plus the two helpers used everywhere else:
 *
 *   listen(name, handler)      -- subscribe to a server event ("on")
 *   emitRequest(name, payload) -- emit a client request ("emit")
 *
 * Both helpers feed the event panel in index.html.
 */
(function (global) {
  "use strict";

  const store = global.GlassworksStore;
  const socket = global.io({
    autoConnect: false,
    transports: ["websocket", "polling"],
  });

  function reactionFor(name, payload) {
    if (name === "state.synced") {
      return "snapshot stored";
    }
    if (name === "operation.rejected") {
      const reason =
        payload && payload.reason ? payload.reason : "unknown reason";
      return "rejected: " + reason;
    }
    if (name === "connect") {
      return "connected";
    }
    if (name === "disconnect") {
      return "offline";
    }
    if (name === "connect_error") {
      return "connection error";
    }
    if (payload && payload.state) {
      return "state updated";
    }
    return "no reaction";
  }

  function logIncoming(name, payload) {
    if (store) {
      store.logEvent("down", name, payload, reactionFor(name, payload));
    }
  }

  function listen(name, handler) {
    socket.on(name, (payload) => {
      logIncoming(name, payload);
      if (handler) {
        handler(payload);
      }
    });
  }

  function emitRequest(name, payload) {
    const data = payload == null ? {} : payload;
    socket.emit(name, data);
    if (store) {
      store.logEvent("up", name, data, "request sent");
    }
  }

  socket.on("connect", () => {
    if (store) {
      store.state.connected = true;
      store.state.lastError = null;
    }
    logIncoming("connect", { cause: "connection" });
  });

  socket.on("disconnect", (reason) => {
    if (store) {
      store.state.connected = false;
    }
    logIncoming("disconnect", { cause: "connection", reason: reason });
  });

  socket.on("connect_error", (error) => {
    if (store) {
      store.state.connected = false;
      store.state.lastError = error && error.message ? error.message : "connection error";
    }
    logIncoming("connect_error", {
      cause: "connection",
      message: error && error.message ? error.message : "connection error",
    });
  });

  function connect(role) {
    if (store) {
      store.state.role = role;
      store.state.lastError = null;
      // The handshake auth is the one client-to-server payload in Phase 2.
      // Logging it here makes the ⬆ emit side of the event panel visible
      // before gameplay requests arrive in later phases.
      store.logEvent(
        "up",
        "connect",
        { role: role, cause: "client" },
        "auth sent"
      );
    }
    socket.auth = { role: role };
    socket.connect();
  }

  function disconnect() {
    socket.disconnect();
  }

  // Convenience globals, matching the helper names used by the event panel.
  global.listen = listen;
  global.emitRequest = emitRequest;
  global.GlassworksSocket = {
    socket,
    listen,
    emitRequest,
    connect,
    disconnect,
  };
})(window);
