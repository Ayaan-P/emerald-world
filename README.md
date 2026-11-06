# Emerald World

A native PC Pokémon Emerald world built from [pret's decompilation](https://github.com/pret/pokeemerald) and the [NTx86 SDL2 port](https://github.com/NTx86/pokeemerald-sdl2pc). Trainers share a world while keeping their own Pokémon, inventory, story progress and saves. The browser launcher manages sessions. The game runs in a separate native window.

## Start here

- **Players:** [RC6 features and player flow](docs/RELEASE_RC6.md), [Linux player installation](docs/linux-packaging.md).
- **Developers and agents:** [development rules and port invariants](CLAUDE.md), [native build instructions](INSTALL_PC.md).
- **Finding the right document:** [documentation index](docs/README.md).
- **What landed versus what is next:** [integration status](docs/INTEGRATION_STATUS.md).

## Main, candidates and published downloads

`main` contains the integrated RC5 feature stack and the polished RC6 NPC, interaction-graph and live director work, promoted through [PR #205](https://github.com/Ayaan-P/emerald-world/pull/205). Start new work from `origin/main` and target PRs to `main`.

The published Linux player archive is [v0.2.0-rc.5](https://github.com/Ayaan-P/emerald-world/releases/tag/v0.2.0-rc.5). RC6 source being on main does **not** mean an RC6 download has been published. Check [GitHub Releases](https://github.com/Ayaan-P/emerald-world/releases) for actual assets and tags. An old installed shortcut may still point to an older checkout or package.

`vanilla` preserves the upstream port. `rc` and the RC4 experiments are historical, not alternate current baselines. Do not copy the unfinished RC4 battle-engine transplant into main. Mega Evolution and an expanded National Dex are not included in this release scope.

## Available in the integrated source

- Shared exploration, consent-based tag/co-op activities, private trainer saves, chat, friend travel and existing trade/PvP paths. Presence capacity, sprite capacity and battle participant counts are different limits; none is a new load-test result.
- Persistent generated caves with authored wildlife, and outdoor areas using existing Hoenn art and Route 101 encounters. One generated area is active per authority; everyone must leave before switching.
- Outdoor guides and casts of up to three native characters with fixed authored dialogue.
- Director-published interactive adventures with state-dependent NPC dialogue. An owner can change one admitted trainer's temporary state or interaction rule and query client-reported outcomes.
- A React launcher with local continuation, saved-area selection, explicit generation-cost confirmation, private save backups and recovery guidance.
- Inherited rally, DexNav and repeat-Repel functionality. Their specific progression and encounter limits remain separate from generated-area acceptance.

Guides/casts are not automatically interactive adventures. Opening an adventure does not start an autonomous director. Adventure state is per trainer and per visit, not durable shared quest progress. There are no new quest reward actions, generated artwork or authored trainer battles. See [RC6 scope](docs/RELEASE_RC6.md) for the full boundary.

### Evidence, not blanket certification

Combined Linux native and React builds and focused real native/socket and browser journeys have passed locally. Those journeys include area entry/return, an authored NPC transition, live owner state/rule changes with applied reports and observed native transitions, named adventure selection and private save backup. RC5 also received direct maintainer playtesting.

This is not a full-campaign, new Windows/macOS, WAN/load or autonomous-GM certification. Full six-party co-op rotation, medicine targeting/consumption and catch-to-storage remain unverified in the integrated candidate. Implemented features are not necessarily fully accepted features.

[GitHub Actions](https://github.com/Ayaan-P/emerald-world/actions) is the current CI source. A merge or old green run is not evidence that the current revision is green. [Historical co-op evidence](docs/COOP_STATUS.md) is retained with its original scope, not promoted into current acceptance claims.

## Build and open the source launcher on Linux

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

## Play an expedition

1. Open a local expedition or create a clearly labeled new world/save. Continue reuses the displayed trainer. A new trainer starts the normal introduction and needs a Pokémon before exploring.
2. Generate an area with explicit model-use confirmation, or select an existing area or director-published adventure. Selecting saved content does not call a model.
3. In the native game, stand outdoors/on foot with a conscious non-Egg Pokémon. Open **START → WORLD → Explore generated area**.
4. Face a character and press **A** to talk. Keyboard defaults: arrows to move, **Z** for A, **X** for B, **Enter** for START. Chat uses **T**, or **Ctrl+T** when T is a game binding. **Esc** cancels typing.
5. Return with **WORLD → Leave generated area**, then save through the normal game menu. Closing or restarting discards unsaved progress. Saved terrain and saved trainer progress are different things.

Local hosting ends when its launcher exits. Persistent dedicated hosting is separate. Do not launch two games on the same trainer save. Use **Save backups** on a stopped profile before experimenting. Backups contain trainer save bytes, not the server world, account credentials or durable adventure progress.

## Contributing

Branch from current main, keep changes focused and record actual verification. Use disposable worlds for development, not a running human session. Preserve native battle/save/world ownership boundaries. Do not treat stale draft titles as a missing-feature list: many original stacked PRs were incorporated by an integration PR.

[CLAUDE.md](CLAUDE.md) describes the development conventions and low-level engine invariants. Historical design/evidence documents remain under `docs/`; [the index](docs/README.md) distinguishes them from current guidance.
