# Kanto-only source overlay for RC9

Base application: `integrate/rc9` at `73af5021705d67f65c9d5a9e510ba35d35a6902a`. Base engine: RC9 checkpoint `2024a83db5242783c0f9ae93f8381271045e7037`. The three published handoff patches reconstruct tree `181a0eb3bdb9f9bc110c8c112a3d9109bf3e6cb6`; all 77 manifest file hashes and the incremental patch hash were checked.

Reconstruct the engine from upstream `bb3fd057061cdd7e6a9e79b76abb41924ee44ecc` using the three patches in `docs/attempt-handoffs/rc7`, in their documented order. Then run `git apply --check /path/to/port/kanto-on-rc9/engine.patch` before applying this overlay. RC9 already contains the RC8 engine work. Do not apply `port/rc8-on-rc7/engine.patch` again.

This overlay carries the prior combined-map generator and native regional-save extension plus the new content selection, upstream story-entry hook and interpreter tests. It does not change the RC9 submodule pin, the published handoff patches, the native fixed-memory layout checks, Maya's integration branch or the earlier Kanto PR. The normal build wrapper still requires trusted engine ancestry; reconstructing source bytes does not supply that history.

See `docs/KANTO_MULTIREGION_DRAFT.md` for commands, save compatibility and remaining blockers. The patch is source integration, not a playable Kanto release.
