# Emerald World

A native PC Pokémon Emerald world built from [pret's decompilation](https://github.com/pret/pokeemerald) and the [NTx86 SDL2 port](https://github.com/NTx86/pokeemerald-sdl2pc). Trainers share a world while keeping their own Pokémon, inventory, story progress and saves. The browser launcher manages sessions. The game runs in a separate native window.

## Start here

- **Players:** [RC10 version and source handoff](docs/RC10_EXPANSION_HANDOFF.md), [Linux player installation](docs/linux-packaging.md).
- **Developers and agents:** [development rules and port invariants](CLAUDE.md), [native build instructions](INSTALL_PC.md).
- **Finding the right document:** [documentation index](docs/README.md).
- **What landed versus what is next:** [integration status](docs/INTEGRATION_STATUS.md).

## Current release and source

This branch is the **RC12 multiplayer field-activities candidate**, not a released build or a claim of completed native QA. It contains the cumulative app stack #279–283 on app main `80b14ebfbfd4dd4da2dc16d886a37f0db1f45516` and pins the paired native privacy client `984165808a45aaaaa7c7169c228ef1a1480ab6d0` (#23). Pulling source does not update an installed package or shortcut. See [candidate handoff](INSTALL_PC.md#rc12-cumulative-candidate-handoff) for exact dependencies, player entry and remaining checks.

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

## Cooperative field stories (RC12 candidate)

This draft pairs private two-player clues with persistent local story choices.
It requires the matched COMMANDS1 native client and server from the RC12 private
command candidate. It does not change a player's party, money, items or save.

For a local world, open its host and select **Content workshop → Cooperative
field story (RC12)**. Preview shows the exact two-part content and station list.
Save and close connected games, review the preset, then apply it. Both parts
are installed in one database transaction. Existing maps, residents and player
progress are preserved; reinstalling identical content does not reset a run.
The preset stations pass static checks against the released Expansion layout
bytes: clear ground, connected paths and no authored NPC overlap. Rendered
two-client QA is still required before public deployment. Versioned preset IDs
leave any older installed prototype and its progress untouched.

Hosted-world owners can use the existing owner API with
`{"command":"publish_field_story","bundle":{"mystery":...,"story":...}}`.
The bundled preset is available from `world.field_story_bundle.curated()` and
matches `examples/cooperative_signal.json` plus
`examples/cooperative_signal_story.json`. This is an owner operation, not a
player chat command. Conflicting immutable IDs reject the whole installation.
Never give players owner credentials.

1. One player types `/mystery start signal_v2` and shares the displayed invitation
   with their chosen partner. The partner uses `/mystery join CODE`.
2. Each player uses `/mystery status`, travels to their own station and reads
   `/mystery clue`. Clues are private. Tell your partner what you learned.
3. The designated solver uses the displayed `/mystery solve STAGE ANSWER` line.
   Both players must be present at their stations and have read their clues.
   Solving advances both players. `/mystery leave` ends the run for both.
4. After both stages, either participant can read `/story signal_after_v2` in
   Rustboro and choose whether to restore the warning relay or archive its
   message. Other visitors then see the resulting local story. The relay is
   narrative state, not a newly placed map object or a changed transport route.

Run progress, both participants' completion, and the resulting place story
survive server restarts. A resumed run still needs fresh player positions.
`/mystery list` lists published mysteries and `/story` lists available local
stories. Private choices are not posted to room chat. The owner can inspect the
world database, so this is player-to-player privacy, not secrecy from the host.

Authors can reuse the system with two roles, up to twelve paired clue stages,
and story scenes with a `mystery` prerequisite. Only actual participants in a
completed run satisfy that prerequisite. The server evaluates availability and
commits choices with idempotent receipts; agents author content rather than
asserting that a player completed it.

## RC12 candidate: cooperative field relays

Two to four guildmates can run ordered checkpoints, physically pass a baton on
adjacent pads and improve durable private team times. The included Petalburg
circuit needs no story pack or save changes. The launcher Content workshop lists
courses and the player loop; [player instructions](world/PLAYER_CLIENT.md#rc12-candidate-cooperative-field-relays)
cover joining, countdowns, handoffs and cancellation. Requires the paired RC12
private-command client. Source/authority tests are not rendered gameplay QA.

## Contributing

Branch from current main, keep changes focused and record actual verification. Use disposable worlds for development, not a running human session. Preserve native battle/save/world ownership boundaries. Do not treat stale draft titles as a missing-feature list: many original stacked PRs were incorporated by an integration PR.

[CLAUDE.md](CLAUDE.md) describes the development conventions and low-level engine invariants. Historical design/evidence documents remain under `docs/`; [the index](docs/README.md) distinguishes them from current guidance.
