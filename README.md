# Emerald World

A native PC Pokémon Emerald world built from [pret's decompilation](https://github.com/pret/pokeemerald) and the [NTx86 SDL2 port](https://github.com/NTx86/pokeemerald-sdl2pc). Trainers share a world while keeping their own Pokémon, inventory, story progress and saves. The browser launcher manages sessions. The game runs in a separate native window.

## Start here

- **Players:** [RC9 features and player flow](docs/RELEASE_RC9.md), [Linux player installation](docs/linux-packaging.md).
- **Developers and agents:** [development rules and port invariants](CLAUDE.md), [native build instructions](INSTALL_PC.md).
- **Finding the right document:** [documentation index](docs/README.md).
- **What landed versus what is next:** [integration status](docs/INTEGRATION_STATUS.md).

## Current release and source

`main` contains RC9, combining the Expansion-native game with shared generated worlds. See [RC9 scope and installation](docs/RELEASE_RC9.md) and [GitHub Releases](https://github.com/Ayaan-P/emerald-world/releases) for published player packages. Source changes do not update an installed package or shortcut.

RC9 starts a fresh Expansion campaign with matching clients. It includes shared exploration and tagged co-op, the modern species catalogue, generated caves and outdoor areas, guilds and independent trainer saves. Imported species data is not proof of every mechanic or encounter. Kanto and newer trading additions are outside RC9's release scope.

Expansion and vanilla have separate binaries, profiles and protocol cohorts. Never import an older vanilla save into the RC9 Expansion campaign. The vanilla source remains in `src/`; the Expansion engine is pinned under `engines/expansion-native`. Its current source reconstruction and verification boundaries are recorded in [the source handoff](docs/attempt-handoffs/rc7/CURRENT.md).

## Launcher and game

- **Play:** choose Local or Hosted, or open a named saved game. Solo saves are always available separately.
- **Local worlds:** run on this computer. Create and play, or set up generated areas first. Creation does not expose an Internet server. Stop host disconnects that world's players; Disconnect only detaches your session. Local authorities keep running until stopped or the launcher quits.
- **Hosted worlds:** join with a private player invitation. Owner access is separate and lets you manage a configured dedicated service, such as a Hetzner server. The launcher does not provision or deploy that server.
- **Explore:** open a local world, generate a cave or outdoor area, or select saved content. Generation uses a supported signed-in model CLI and may incur charges. Reopening saved areas makes no model call. Remote hosted worlds are not editable here.
- **Controls & help:** keyboard controls, co-op, the native WORLD menu and recovery. Gameplay, guilds, friend travel, DexNav and wild shuffle remain in the native game.
- **Save backups:** export a stopped trainer's save. Owner-account credentials and server-world data are separate backups.

A selected launcher session is not proof that the native game is connected. Game connection and nearby trainers use fresh native telemetry. In-page preview is optional; the native game still runs separately.

## Build and open the vanilla source launcher on Linux

Use system Python 3.11+, a C/C++ toolchain, GNU make, pkg-config, libpng and SDL2. The sandboxed desktop game also needs Bubblewrap, Xephyr, a browser and X11/XWayland with permitted user namespaces. The React source build needs Node.js/npm. Install dependencies explicitly using [INSTALL_PC.md](INSTALL_PC.md); nothing below installs system packages.

```sh
git clone --branch main https://github.com/Ayaan-P/emerald-world.git
cd emerald-world

# Review the pinned asset manifest before this explicit network restore.
python3 scripts/restore_upstream_assets.py
python3 scripts/restore_upstream_assets.py --check
make -j"$(nproc)" linux CFLAGS=-g WERROR=1

cd launcher-web
npm ci
npm run build
cd ..
python3 -m world.web_launcher --binary "$PWD/pokeemerald64"
```

The explicit `--binary` avoids accidentally selecting an older `build/pokeemerald64`. Generated build inputs and executables stay out of Git. On unusual toolchains, inspect the commands and `build/<target>/build_flags.txt` rather than assuming a successful build used the expected feature gates.

The tkinter launcher remains a legacy/operator fallback. Its old UI labels are not the React player's instructions. For dedicated server operation and private invitations, see [deploy/README.md](deploy/README.md). A packaged player install needs neither npm nor a source checkout; use [the package guide](docs/linux-packaging.md).

## Enter a generated area

1. Create or open a local world. Play reuses its displayed trainer. A new trainer starts the normal introduction and needs a Pokémon before exploring.
2. Open Explore. Generate an area with explicit model-use confirmation, or select a saved area or published adventure. Selecting saved content does not call a model.
3. In the native game, stand outdoors/on foot with a conscious non-Egg Pokémon. Open **START → WORLD → Explore generated area**.
4. Face a character and press **A** to talk. Keyboard defaults: arrows to move, **Z** for A, **X** for B, **Enter** for START. Chat uses **T**, or **Ctrl+T** when T is a game binding. **Esc** cancels typing.
5. Return with **WORLD → Leave generated area**, then save through the normal game menu. Closing or restarting discards unsaved progress. Saved terrain and saved trainer progress are different things.

Disconnecting does not stop a local host. Use Stop host in Local worlds or Quit launcher. Persistent dedicated hosting is separate. Do not launch two games on the same trainer save. Use **Save backups** on a stopped profile before experimenting. Backups contain trainer save bytes, not the server world, account credentials or durable adventure progress.

## Contributing

Branch from current main, keep changes focused and record actual verification. Use disposable worlds for development, not a running human session. Preserve native battle/save/world ownership boundaries. Do not treat stale draft titles as a missing-feature list: many original stacked PRs were incorporated by an integration PR.

[CLAUDE.md](CLAUDE.md) describes the development conventions and low-level engine invariants. Historical design/evidence documents remain under `docs/`; [the index](docs/README.md) distinguishes them from current guidance.
