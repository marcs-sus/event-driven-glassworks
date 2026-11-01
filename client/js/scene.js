/*
 * Phaser scene: the village ground comes from the Tiled map and tileset in
 * client/assets.  Furnaces and benches are drawn from the latest server
 * snapshot; the client never derives game state.
 */
(function (global) {
  "use strict";

  const Phaser = global.Phaser;

  const PIECE_LABELS = {
    furnace_heating: "heating",
    furnace_ready: "ready",
    bench_working: "working",
    bench_cooling: "cooling",
  };

  class VillageScene extends Phaser.Scene {
    constructor() {
      super("VillageScene");
    }

    preload() {
      this.load.image("tileset-village", "/assets/tileset-vila.png");
      this.load.tilemapTiledJSON("village", "/assets/vila.json");
    }

    create() {
      const map = this.make.tilemap({ key: "village" });
      const tileset = map.addTilesetImage("tileset-village", "tileset-village");
      this.groundLayer = map.createLayer("ground", tileset, 0, 0);
      this.groundLayer.setDepth(0);

      this.furnaceGroup = this.add.group();
      this.benchGroup = this.add.group();

      this.statusText = this.add
        .text(16, 14, "", {
          fontFamily: "ui-monospace, monospace",
          fontSize: "16px",
          color: "#f5e6c8",
          backgroundColor: "#120e0bcc",
          padding: { x: 10, y: 6 },
        })
        .setDepth(20);

      this.hintText = this.add
        .text(16, 610, "Furnaces above · benches below", {
          fontFamily: "ui-monospace, monospace",
          fontSize: "13px",
          color: "#c9b8a2",
          backgroundColor: "#120e0bcc",
          padding: { x: 8, y: 4 },
        })
        .setDepth(20);

      if (this.game._pendingState) {
        this.showState(this.game._pendingState);
        this.game._pendingState = null;
      }
    }

    pieceLabel(piece) {
      const label = PIECE_LABELS[piece.state] || piece.state;
      return "#" + piece.id + " " + label;
    }

    makeStation(x, y, title, status, color, piece) {
      const container = this.add.container(x, y);
      const glow = this.add.circle(0, 0, 46, color, 0.16);
      const body = this.add
        .rectangle(0, 0, 82, 60, color, 0.92)
        .setStrokeStyle(3, 0xffe6b0, 0.75);
      const titleText = this.add
        .text(0, -52, title, {
          fontFamily: "ui-monospace, monospace",
          fontSize: "15px",
          color: "#ffe6b0",
        })
        .setOrigin(0.5);
      const statusText = this.add
        .text(0, 40, status, {
          fontFamily: "ui-monospace, monospace",
          fontSize: "13px",
          color: "#ffffff",
        })
        .setOrigin(0.5);

      container.add([glow, body, titleText, statusText]);

      if (piece && piece.state === "furnace_ready") {
        this.tweens.add({
          targets: glow,
          alpha: { from: 0.12, to: 0.48 },
          duration: 700,
          yoyo: true,
          repeat: -1,
        });
      }

      return container;
    }

    showState(snapshot) {
      if (!snapshot) {
        return;
      }
      if (!this.furnaceGroup || !this.benchGroup || !this.statusText) {
        // The scene is still preloading; keep the latest snapshot for create().
        this.game._pendingState = snapshot;
        return;
      }

      this.tweens.killAll();
      this.furnaceGroup.clear(true, true);
      this.benchGroup.clear(true, true);

      const furnaces = snapshot.furnaces || [];
      const benches = snapshot.benches || [];
      const pieces = snapshot.pieces || {};

      furnaces.forEach((furnace, index) => {
        const piece =
          furnace.piece_id == null
            ? null
            : pieces[String(furnace.piece_id)] || null;
        const station = this.makeStation(
          150 + index * 190,
          120,
          "Furnace " + furnace.id,
          piece ? this.pieceLabel(piece) : "free",
          0xd9772f,
          piece
        );
        this.furnaceGroup.add(station);
      });

      benches.forEach((bench, index) => {
        const piece =
          bench.piece_id == null
            ? null
            : pieces[String(bench.piece_id)] || null;
        const station = this.makeStation(
          150 + index * 190,
          480,
          "Bench " + bench.id,
          piece ? this.pieceLabel(piece) : "free",
          0x4d8fc4,
          piece
        );
        this.benchGroup.add(station);
      });

      const season = snapshot.season_open
        ? "Season " + snapshot.season
        : "No season (last: " + snapshot.season + ")";
      const workers = snapshot.glassblowers || { busy: 0, total: 8, free: 8 };
      this.statusText.setText(
        season +
          "  ·  sand " +
          snapshot.sand +
          "/30  ·  glass " +
          snapshot.glass +
          "  ·  glassblowers " +
          workers.busy +
          "/" +
          workers.total
      );
    }
  }

  function createGame() {
    // Vue replaces the contents of #app when it mounts, so the Phaser game is
    // created from main.js's mounted hook, after the canvas parent exists.
    if (global.game) {
      return global.game;
    }

    const game = new Phaser.Game({
      type: Phaser.AUTO,
      parent: "game-canvas",
      width: 960,
      height: 640,
      backgroundColor: "#120e0b",
      scene: [VillageScene],
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      render: {
        pixelArt: true,
        antialias: false,
      },
    });

    // Required by the rubric: the Vue shell can hand any snapshot to Phaser.
    game.showState = function (snapshot) {
      const scene = game.scene.getScene("VillageScene");
      if (scene && scene.showState) {
        scene.showState(snapshot);
      } else {
        game._pendingState = snapshot;
      }
    };

    global.game = game;
    return game;
  }

  global.GlassworksScene = { VillageScene, createGame };
})(window);
