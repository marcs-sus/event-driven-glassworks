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
        const noticeValue = typeof reaction === "function"
          ? reaction(payload || {})
          : reaction;
        this.store.notice = noticeValue;
        setTimeout(() => {
          if (this.store.notice === noticeValue) {
            this.store.notice = null;
          }
        }, 3000);
      };

      socket.listen(
        "state.synced",
        applyFact(() => "stores the state and renders the village")
      );
      socket.listen(
        "glassworks.started",
        applyFact(
          (payload) => "opens season " + payload.state.season + " on the HUD"
        )
      );
      socket.listen(
        "glassworks.closed",
        applyFact(
          (payload) =>
            payload.causa === "master_disconnected"
              ? "marks the season closed after the Master left"
              : "marks the season closed and keeps " + payload.state.glass + " glass"
        )
      );
      socket.listen(
        "glassmaking.started",
        applyFact(
          (payload) => "highlights furnace " + payload.furnace_id + " as heating"
        )
      );
      socket.listen(
        "glassmaking.heated",
        applyFact(
          (payload) => "marks furnace " + payload.furnace_id + " as ready to move"
        )
      );
      socket.listen(
        "glassmaking.bench_started",
        applyFact(
          (payload) => "moves the piece to bench " + payload.bench_id
        )
      );
      socket.listen(
        "glassmaking.completed",
        applyFact(
          (payload) => "starts cooling on bench " + payload.bench_id + " and frees a glassblower"
        )
      );
      socket.listen(
        "glass.stored",
        applyFact(
          (payload) => "adds one glass to the stock"
        )
      );
      socket.listen(
        "glass.cracked",
        applyFact(
          (payload) => "shows the cracked piece and its " + Number(payload.crack_chance).toFixed(0) + "% chance"
        )
      );
      socket.listen(
        "sand.stored",
        applyFact(
          (payload) => "adds " + payload.gained + " sand to the stock"
        )
      );
      socket.listen(
        "furnace.purchased",
        applyFact(() => "renders a new furnace on the map")
      );
      socket.listen(
        "bench.purchased",
        applyFact(() => "renders a new bench on the map")
      );
      socket.listen("operation.rejected", (payload) => {
        this.store.lastError = payload.reason || "request rejected";
        const noticeValue = "Rejected: " + (payload.reason || "request rejected");
        this.store.notice = noticeValue;
        setTimeout(() => {
          if (this.store.notice === noticeValue) {
            this.store.notice = null;
          }
        }, 3000);
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
