/*
 * Vue shell: login overlay, HUD skeleton, event panel wiring and the bridge
 * from server snapshots to the Phaser scene.
 */
(function (global) {
  "use strict";

  const { createApp } = global.Vue;
  const store = global.GlassworksStore;
  const socket = global.GlassworksSocket;

  const app = createApp({
    data() {
      return { store: store.state };
    },
    computed: {
      snapshot() {
        return this.store.snapshot;
      },
      seasonLabel() {
        if (!this.snapshot) {
          return "—";
        }
        return this.snapshot.season_open
          ? "Season " + this.snapshot.season
          : "Closed";
      },
      sandLabel() {
        return this.snapshot ? this.snapshot.sand + " / 30" : "—";
      },
      glassLabel() {
        return this.snapshot ? String(this.snapshot.glass) : "—";
      },
      workerLabel() {
        if (!this.snapshot) {
          return "—";
        }
        const workers = this.snapshot.glassblowers;
        return workers.busy + " busy · " + workers.free + " free";
      },
      roleLabel() {
        if (!this.store.role) {
          return "—";
        }
        return this.store.role === "master" ? "Master" : "Player";
      },
      connectionLabel() {
        return this.store.connected
          ? "Connected as " + this.roleLabel
          : "Disconnected";
      },
      canOpenSeason() {
        return !!this.snapshot && !this.snapshot.season_open;
      },
      canCloseSeason() {
        return !!this.snapshot && this.snapshot.season_open;
      },
    },
    mounted() {
      if (global.GlassworksScene && global.GlassworksScene.createGame) {
        global.GlassworksScene.createGame();
      }

      const applyFact = (reaction) => (payload) => {
        if (payload && payload.state) {
          store.applySnapshot(payload.state, payload.causa);
          if (global.game) {
            global.game.showState(payload.state);
          }
        }
        this.store.lastError = null;
        this.store.notice =
          typeof reaction === "function"
            ? reaction(payload || {})
            : reaction;
      };

      socket.listen(
        "state.synced",
        applyFact(() => "State synchronized.")
      );
      socket.listen(
        "glassworks.started",
        applyFact(
          (payload) => "Season " + payload.state.season + " is open."
        )
      );
      socket.listen(
        "glassworks.closed",
        applyFact(
          (payload) =>
            "Season closed with " + payload.state.glass + " glass stored."
        )
      );
      socket.listen(
        "glassmaking.started",
        applyFact(
          (payload) => "Furnace " + payload.furnace_id + " is heating."
        )
      );
      socket.listen(
        "glassmaking.heated",
        applyFact(
          (payload) => "Furnace " + payload.furnace_id + " piece is ready."
        )
      );
      socket.listen(
        "glassmaking.bench_started",
        applyFact(
          (payload) =>
            "Piece moved from furnace " +
            payload.furnace_id +
            " to bench " +
            payload.bench_id +
            "."
        )
      );
      socket.listen(
        "glassmaking.completed",
        applyFact(
          (payload) =>
            "Bench " +
            payload.bench_id +
            " is cooling; a glassblower is free."
        )
      );
      socket.listen(
        "glass.stored",
        applyFact(
          (payload) =>
            "One glass stored (stock " + payload.state.glass + ")."
        )
      );
      socket.listen(
        "glass.cracked",
        applyFact(
          (payload) =>
            "The piece cracked (" +
            Number(payload.crack_chance).toFixed(0) +
            "% chance)."
        )
      );
      socket.listen(
        "sand.stored",
        applyFact(
          (payload) =>
            "Sand +" +
            payload.gained +
            " (stock " +
            payload.state.sand +
            "/30)."
        )
      );
      socket.listen(
        "furnace.purchased",
        applyFact(() => "adds a new furnace to the village")
      );
      socket.listen(
        "bench.purchased",
        applyFact(() => "adds a new bench to the village")
      );
      socket.listen("operation.rejected", (payload) => {
        this.store.lastError = payload.reason || "request rejected";
        this.store.notice =
          "Rejected: " + (payload.reason || "request rejected");
      });
    },
    methods: {
      join(role) {
        socket.connect(role);
      },
      leave() {
        socket.disconnect();
      },
      openSeason() {
        store.startSeason();
      },
      closeSeason() {
        store.closeSeason();
      },
      purchaseFurnace() {
        store.purchaseFurnace();
      },
      purchaseBench() {
        store.purchaseBench();
      },
      clearEvents() {
        store.clearEvents();
      },
    },
  });

  app.mount("#app");
})(window);
