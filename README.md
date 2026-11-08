# Emerald World

A native PC Pokémon Emerald world built from [pret's decompilation](https://github.com/pret/pokeemerald) and the [NTx86 SDL2 port](https://github.com/NTx86/pokeemerald-sdl2pc). Trainers share a world while keeping their own Pokémon, inventory, story progress and saves. The browser launcher manages sessions. The game runs in a separate native window.

## Start here

- **Players:** [RC10 version and source handoff](docs/RC10_EXPANSION_HANDOFF.md), [Linux player installation](docs/linux-packaging.md).
- **Developers and agents:** [development rules and port invariants](CLAUDE.md), [native build instructions](INSTALL_PC.md).
- **Finding the right document:** [documentation index](docs/README.md).
- **What landed versus what is next:** [integration status](docs/INTEGRATION_STATUS.md).

## Current release and source

`main` contains **RC10**, including the rc10.10 multiplayer and native-engine fixes. The app pins the matching source in [Ayaan-P/pokeemerald-expansion-native](https://github.com/Ayaan-P/pokeemerald-expansion-native), whose default `main` branch carries that engine checkpoint. See [the RC10 handoff and build instructions](docs/RC10_EXPANSION_HANDOFF.md). Published downloadable packages on [GitHub Releases](https://github.com/Ayaan-P/emerald-world/releases) currently remain RC9; pulling source does not update an installed package or shortcut.

For an existing source checkout:

```sh
git pull origin main
git submodule sync --recursive
git submodule update --init --recursive
```

RC10 retains the Expansion campaign, shared exploration and tagged co-op, modern species catalogue, generated areas, guilds and independent trainer saves. It adds reviewed world/personal settings and the native battle, capture/naming, PC, WORLD menu, co-op admission and scheduling fixes. When a Repel expires, the native game can offer another owned Repel; with multiple strengths, choose one from the menu, and with a single strength, confirm its use. You can decline, and the game only consumes the selected item after rechecking that it is still available. World permissions still require eligible Pokémon and equipment; test-kit Pokémon/items are not bundled into fresh saves. Kanto and unfinished world-history/multi-place drafts are not included.

Expansion and vanilla have separate binaries, profiles and protocol cohorts. Do not import older vanilla saves into Expansion. The root `src/` is the older engine; RC10 game-side development belongs under `engines/expansion-native/src/world/` and that submodule's `include/platform/`. Build RC10 with `scripts/build_expansion.py` as described in the handoff, not the vanilla command below.

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
