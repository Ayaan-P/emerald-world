# Combined RC9 Implementation Plan

> **For Hermes:** Parent owns integration; independently owned workers may adapt acceptance journeys. No edits to Dot originals or donor. Preserve human saves, installed desktop and RC8 releases.

**Goal:** Ship the current Expansion RC7 multiplayer engine plus Dot PR237's RC8 generated-world capabilities as RC9.

**Architecture:** Checkpoint current verified RC7 before creating integrate/rc9 and integrate/rc9-world. Merge PR237 application changes, but apply its source-only engine delta onto current engine9506377, not its older gitlink. Preserve existing CAVE10/11 wildlife and negotiate XL as CAVE16.

**Tech Stack:** Native portable C/SDL2, Python world authority/browser launcher, existing trusted sysroot/toolchain, GitHub releases.

## 1. Preserve and combine
- Refresh docs/attempt-handoffs/rc7 source patch/manifest against current clean tracked engine and verify three-patch reconstruction with a temporary Git index.
- Commit the already exercised launcher/package/presentation checkpoint and packaged-game evidence. No separate RC7 publication.
- Create owned RC9 branches; merge origin/dot/rc8-on-rc7 at312f6f0. Apply port/rc8-on-rc7/engine.patch to the newer engine. Preserve ignored inputs and peer-owned untracked checker.

## 2. XL memory tracer bullet
- Test current patched engine backing storage object/ELF: XL buffer must not consume additional fixed 256KiB EWRAM; default/GBA behavior stays intact.
- Read fieldmap initialization and native reset contracts before changing src/fieldmap.c. Prefer guarded native-only host backing storage, not weakening gba_regions.ld assertions.
- Verify buffer capacity and initialization on actual map entry/re-entry. Build keeps relocation, pointer/layout and battle-script checks enabled.

## 3. Browser cohort tracer bullet
- Add regression in test/world/test_web_launcher.py proving Expansion authoring selects compiler-derived expansion-native cohort, and version16 labels XL while10/11 label wildlife caves.
- Run RED first; minimally fix world/web_launcher.py; run focused browser and species admission tests GREEN.
- RC9 package is Expansion-only; do not inadvertently ship the incompatible legacy vanilla XL capability path.

## 4. Combined build and playable journeys
- Build: python3 scripts/build_expansion.py --development --sysroot /home/ayaan/projects/emerald-world-research/deps/sysroot --multilib-sysroot /home/ayaan/projects/emerald-world-research/worktrees/expansion-foundation/build/expansion-toolchain --jobs6 (spell CLI as --jobs 6).
- Exercise current combined binary: existing run_expansion_release_journey.py ordinary and co-op save/reload journeys using only disposable opening fixture.
- Adapt existing RC8 shared-XL and offline durable-story journeys to actual Expansion launcher/controls; test entry, actual movement/shared identity, return, and offline journal restart. Do not invent outcomes or rewrite expected references to hide failures.
- Assemble with linux_package.py --engine expansion-native. Re-run integrity/preflight and representative actual package journeys. Record binary SHA and precise acceptance scope.

## 5. Source and publication
- Refresh exact engine handoff and RC9 manifest/pin; commit coherent source and push owned integration branch.
- Publish RC9 only after combined build/gameplay evidence. Main promotion via reviewed integration; inspect CI, do not infer success.
- Read back exact remote commit/tag/assets and download/hash archive before reporting publication. Do not install or replace user desktop without request.

## Excluded scope
Trading, unfinished strict dispatcher redesign, Kanto source preparation and optional PR238 world rules are not release prerequisites. Capture/medicine missing acceptance is not a claim they are disabled or broken. Shared XL exploration and offline XL story persistence are distinct supported paths; do not claim synchronized multiplayer XL stories.
