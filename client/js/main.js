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
    },
    mounted() {
      if (global.GlassworksScene && global.GlassworksScene.createGame) {
        global.GlassworksScene.createGame();
      }

      socket.listen("state.synced", (payload) => {
        store.applySnapshot(payload.state, payload.causa);
        if (global.game) {
          global.game.showState(payload.state);
        }
      });

      socket.listen("operation.rejected", (payload) => {
        this.store.lastError = payload.reason || "request rejected";
      });
    },
    methods: {
      join(role) {
        socket.connect(role);
      },
      leave() {
        socket.disconnect();
      },
      clearEvents() {
        store.clearEvents();
      },
    },
  });

  app.mount("#app");
})(window);
