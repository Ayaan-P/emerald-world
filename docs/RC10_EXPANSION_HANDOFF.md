# RC10 Expansion source handoff for Dot / PR #252

## Correct source boundary

The app's active native game is **not** the root `src/platform/` engine.
For RC10 game-side changes use the `engines/expansion-native` submodule:

- App repository: https://github.com/Ayaan-P/emerald-world
- Integration branch: `integrate/rc10-app`
- Expansion repository: https://github.com/Ayaan-P/pokeemerald-expansion-native
- Expansion branch containing the RC10 integration: `integrate/rc10-summary-fix`
- This handoff's exact published source pin: `2c3d08f42e39fea85ccf5bcf77389d04848dd841`
- Matching installed release checkpoint: `0.4.0-rc.10.9`
- That checkpoint's Linux native binary SHA256: `5030e0994803daf0f44925adbbd5d23b7b6d4b48555694db5185747681c77ad0`

Both the submodule gitlink and `scripts/build_expansion.py:PIN` must name that
same commit. `.gitmodules` must point at **Ayaan-P's fork**: the old upstream
URL does not carry these RC10 integration commits. Do not reset the engine to
the upstream donor or port the root engine over Expansion. The runtime includes
native ABI, controller, capture/naming, PC lifecycle and world integration fixes.

This is a stable published checkpoint, not a promise that no later commits exist.
Performance work and two-client May admission verification are proceeding in
parallel. Consume a new published engine pin explicitly; do not rely on a moving
branch as proof of the source used for a release.

## Fetch and verify

New checkout:

```sh
git clone --branch integrate/rc10-app --recurse-submodules https://github.com/Ayaan-P/emerald-world.git
cd emerald-world
git submodule status engines/expansion-native
```

Existing PR #252 checkout (preserve your branch and changes): fetch the updated
base and integrate its pin/config change through the normal branch workflow.
After updating `.gitmodules` and the gitlink:

```sh
git submodule sync -- engines/expansion-native
git submodule update --init engines/expansion-native
git -C engines/expansion-native rev-parse HEAD
git -C engines/expansion-native status --short
```

The first output must equal the pinned commit. The final command should be
empty before claiming a release build. An independent direct source fetch is:

```sh
git clone --branch integrate/rc10-summary-fix https://github.com/Ayaan-P/pokeemerald-expansion-native.git expansion-source
git -C expansion-source checkout --detach 2c3d08f42e39fea85ccf5bcf77389d04848dd841
```

The default app build may still target the old engine. Use the Expansion builder:

```sh
python3 scripts/build_expansion.py --help
python3 scripts/build_expansion.py --sysroot /absolute/existing/development-sysroot --multilib-sysroot /absolute/existing/multilib-sysroot
```

Those are explicit input paths, not directories supplied by Git. The builder
uses installed development tools and existing sysroots; it does not download or
install dependencies. A missing `png.h` requires libpng development headers in
the build environment, not switching engines. Other requirements include the
C/C++ toolchain, SDL2 development metadata, Python, pkg-config, bubblewrap and
32-bit libc/GCC inputs for the mandatory reference/layout checks. Environment
restrictions may still block a build; report the actual error. Do not bypass ABI
checks or sandbox refusals. The compiled feature cohort is in
`engines/expansion.mk`. Outputs go to `build/expansion-native/`.

For an intentional engine development branch, `--development` permits a
descendant of the published pin and reports dirty sources; that is not a clean
pinned release. Do not describe a build as verified until it actually finishes.

## Where PR #252's game-side work belongs

Keep the Python authority/history work in `world/`, the SQLite event history,
place UUIDs and launcher journal. Port the native selection/admission work into:

- `engines/expansion-native/src/world/world_bridge.c`: native wire parsing,
  current shared place/template state and presence.
- `engines/expansion-native/src/world/generated_map.c` and
  `include/platform/generated_map.h`: prepared/shared templates and generated
  entry/exit. These paths already exist; do not create a second map engine.
- `engines/expansion-native/src/world/world_menu.c`: native WORLD UI/selection.
- `engines/expansion-native/src/world/world_activity.c`: pending encounter/field
  ownership; preserve admission and private party semantics.
- `engines/expansion-native/src/world/world_runtime.c`: per-frame integration.
- Corresponding `include/platform/` interfaces inside the submodule.

In contrast, PR #252's root `src/platform/world_bridge.c` and root
`include/platform/generated_map.h` are **not** the Expansion game-side runtime.
Root native tests may be useful specifications, but passing them does not prove
Expansion renders/selects/enters the new places. Inspect and port the semantic
changes; do not blindly copy structures or headers across engine ABIs.

When publishing game-side work, push the Expansion source commit first to a
reachable branch in the Expansion repository, then update the app gitlink and
builder pin together. Preserve original private saves and keep shared history
free of party contents, credentials and private chat.

## Evidence and limits

The pinned source was published and used for a successful Linux native build.
The installed checkpoint includes the idle-RFU guest admission correction.
All three May starter encounter variants passed actual engine co-op capture
preparation in a private fixture; that is **not** a completed bilateral May battle.
User playtests established basic multiplayer battles and modern battle mechanics,
not acceptance of PR #252's multi-place integration.

This handoff does not merge PR #252, deploy its history/schema changes, migrate
any live world, implement region selection in Expansion, or claim that the draft
is ready to play. It removes the source/pin discovery blocker and makes the
correct engine boundary reproducible.
