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

RC10 retains the Expansion campaign, shared exploration and tagged co-op, modern species catalogue, generated areas, guilds and independent trainer saves. It adds reviewed world/personal settings and the native battle, capture/naming, PC, WORLD menu, co-op admission and scheduling fixes. World permissions still require eligible Pokémon and equipment; test-kit Pokémon/items are not bundled into fresh saves. Kanto and unfinished world-history/multi-place drafts are not included.

Expansion and vanilla have separate binaries, profiles and protocol cohorts. Do not import older vanilla saves into Expansion. The root `src/` is the older engine; RC10 game-side development belongs under `engines/expansion-native/src/world/` and that submodule's `include/platform/`. Build RC10 with `scripts/build_expansion.py` using the source setup below. Root `make linux` still builds the historical vanilla engine.

## Launcher and game

- **Play:** choose Local or Hosted, or open a named saved game. Solo saves are always available separately.
- **Local worlds:** run on this computer. Create and play, or set up generated areas first. Creation does not expose an Internet server. Stop host disconnects that world's players; Disconnect only detaches your session. Local authorities keep running until stopped or the launcher quits.
- **Hosted worlds:** join with a private player invitation. Owner access is separate and lets you manage a configured dedicated service, such as a Hetzner server. The launcher does not provision or deploy that server.
- **Explore:** open a local world, generate a cave or outdoor area, or select saved content. Generation uses a supported signed-in model CLI and may incur charges. Reopening saved areas makes no model call. Remote hosted worlds are not editable here.
- **Controls & help:** keyboard controls, co-op, the native WORLD menu and recovery. Gameplay, guilds, friend travel, DexNav and wild shuffle remain in the native game.
- **Save backups:** export a stopped trainer's save. Owner-account credentials and server-world data are separate backups.

A selected launcher session is not proof that the native game is connected. Game connection and nearby trainers use fresh native telemetry. In-page preview is optional; the native game still runs separately.

## Build and open RC10 from source on Linux

Use system Python 3.11+, a C/C++ toolchain, GNU make 4.2+, pkg-config, libpng and SDL2 development files. The 64-bit engine also needs a working 32-bit C toolchain for its mandatory ABI checks. The sandboxed desktop game needs Bubblewrap, Xephyr, a browser and X11/XWayland with permitted user namespaces. The React source build needs Node.js/npm. See [INSTALL_PC.md](INSTALL_PC.md) for dependency guidance. The builder installs nothing and makes no network requests.

```sh
git clone --branch main --recurse-submodules https://github.com/Ayaan-P/emerald-world.git
cd emerald-world

# Checks the engine pin and build dependencies without changing source files.
python3 scripts/build_expansion.py --check
python3 scripts/build_expansion.py --jobs "$(nproc)"

cd launcher-web
npm ci
npm run build
cd ..
python3 -m world.web_launcher --check
python3 -m world.web_launcher
```

The web launcher defaults to Expansion and only discovers `build/expansion-native/pokeemerald-native` for that engine. It never falls back to a vanilla binary. Existing Expansion profiles remain in their separate library. Existing vanilla users can opt in with `--engine vanilla --binary "$PWD/pokeemerald64"`; this does not convert saves.

After the source update commands above, rebuild with `python3 scripts/build_expansion.py`, rebuild `launcher-web`, then run `python3 -m world.web_launcher`. No `/tmp` assets, local checkpoint or private sysroot is required when system dependencies are installed. Developers who deliberately use extracted dependencies can pass `--sysroot` and `--multilib-sysroot` to both the builder and its `--check` mode. Do not use `--development` for an ordinary source build; it explicitly permits uncommitted or descendant engine integration work.

The root vanilla build and its asset-restoration instructions remain in [INSTALL_PC.md](INSTALL_PC.md) for historical port work. They are not RC10 prerequisites. Generated build inputs and executables stay out of Git.

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
