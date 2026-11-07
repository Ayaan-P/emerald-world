# Current RC9 source handoff

Latest target engine: `2024a83db5242783c0f9ae93f8381271045e7037`; exact three-patch tree reconstruction verified. Earlier RC7 milestones below remain historical. The patch now includes Dot PR237 XL/guild/shuffle on top of the final RC7 ownership/presentation fixes, native-only host map backing storage (fixed 256KiB EWRAM checks unchanged), and owned native journal IO.

## Player UI source candidate

`native-player-ui.patch` is an additional source-only patch for the launcher/UI
redesign. Apply it after the three RC9 patches below, or directly to the exact
RC9 engine checkpoint, using `git apply --check` before `git apply`.
`player-ui-source-manifest.json` records the base tree, resulting tree, patch
hash and changed-file hashes. The four-patch reconstruction was verified in a
separate temporary Git index. The existing RC9 gitlink and its provenance are
unchanged. Applying this patch does not replace an installed game binary.

The candidate changes WORLD navigation, connection status, generated-area entry
and exit guidance, feature explanations and action-specific messages. It does
not change battle, save, travel or rally acceptance backends. The matching root
port changes are in `src/platform/world_menu.c` and `world_bridge.c`.

Run `PYTHONPATH=.:test/world python3 -m unittest test_native_world_menu test_native_world_menu_source`
from the app repository. Set
`EW_RC7_ENGINE=/path/to/reconstructed/engine` for the compiled fixture to use
Expansion's actual WORLD source and font widths. The fixture uses simulated
backends, not a game session. It requires working AddressSanitizer,
UndefinedBehaviorSanitizer and LeakSanitizer. In the development sandbox,
LeakSanitizer could not finish under ptrace; that gate is not reported as passed.

Native build, visual inspection and gameplay acceptance are still required.
Build only from the trusted engine ancestry with its normal mandatory checks;
source reconstruction is not permission to bypass those checks. No native
binary, game save or ROM is included in this handoff.

# Current RC7 Expansion source handoff

## Current source

- App branch: `integrate/rc7`. Engine gitlink and JSON manifest are authoritative.
- Engine checkpoint: `9506377d1fff0e1f553caaf66f99550cbd715f59` on local `integrate/rc7-world`.
- Engine is an existing submodule, not another product. Its local commit is not
  fetchable from the upstream URL in `.gitmodules`; the complete source deltas
  are published here so a parent push does not imply a missing object is public.
- No newer Dot branches, human saves, ROM or executable archives are added here.

## Source reconstruction

From a trusted upstream checkout at `bb3fd057061cdd7e6a9e79b76abb41924ee44ecc`,
apply these source patches in order:

1. `native-foundation.patch`
2. `native-world-wip.patch`
3. `native-world-integration-current.patch`

An existing checkout at `e406cf82922e9c3a5bfee746f9a97f67f3916a4c` needs only the third patch.
Use `git apply --check /path/to/patch` before each `git apply`.
The JSON manifest records exact changed-file hashes and incremental patch hash.
All three patches were actually applied to a separate temporary Git index. Its
reconstructed tree exactly equals `374a5938af4354d1d24598ab175fc0692c2cb200`, the current engine source tree.
The working source and its Git index were not reset or modified by that check.

This proves source-byte reconstruction, not original commit ancestry or a fresh
clone build. The build wrapper still enforces its ancestry and mandatory native
checks. Do not bypass them. Trusted ignored toolchain/asset inputs are required.

## Current actual gameplay evidence

- Build22: real two-client tag invitation/consent, native walking into Route101,
  shared wild encounter, battle end through private reward callbacks, then both
  back in unlocked overworld: **PASS**.
- Report: `rc7-rescue/coop-build22-completion/acceptance.json`; binary SHA-256
  `c8b3523894e36808becc40570920b9d4c20e1f57db2e05ce1752fb3fe8656cc7`.
- This narrow pass does **not** establish private EXP amounts, medicine, capture,
  party/PC/Dex/nickname ownership or post-battle save/cold-load.
- Build23 proved separate saves/cold loads but FAILED gameplay correctness:
  the original weak assertion accepted 131,337 bogus EXP (Treecko level5->51).
  This is not accepted private reward behavior, despite that harness's ok:true.
- Source diagnosis: the original PlayerHandleExpUpdate co-op multiplexer was
  missing. Wurmple species265 + level2 encoded as 09010200 was read as 131337 EXP.
  The whole original action dispatch branch is now adapted, not clamped.
- That correction exposed real private reward rendering: build24 crashed in
  CopyGlyphToVRAM because stock end-turn cleanup freed message windows first.
  The original HandleEndTurn_FinishBattle co-op resource-preserving exit guard
  is now adapted too. Build26 PASSED the actual shared-win/private-EXP/normal
  save/cold-Continue journey. Both private Pokemon kept identity, gained modest
  EXP (149->174, level5 unchanged) and retained it after independent cold loads.
  This still does not accept medicine/capture/full-team edge cases.
- Source also integrates compiler-derived enabled species and explicit CAVE10/11
  cohort identity, with modern/legacy wildlife admission isolated. Focused
  canonical catalogue, native-wire digest and cross-cohort tests passed.
- Earlier separate passes: ordinary two-player battle build16, independent
  save/cold Continue build18, generated-area interaction/exit primary build15.
  They are not automatically current-binary regression passes.
- Historical failed build19-22 reports remain evidence, not the current outcome.

## Release closure

This is a source checkpoint, not a completed RC7 release. Current closure work
includes remaining original controller/action ownership parity, species-cohort
integration, actual Expansion package launch/profile routing, current-binary
acceptance and publication. Trading and newer Dot work remain excluded.
The original-to-Expansion contract map is `docs/RC7_PORT_CONTRACT.md`.

## Subsequent original-contract closure (builds27–29)

- Restored full-six callback1 mutation barrier, disconnect menu close, hidden
  reserve eligibility and absolute guest friendship publication.
- Restored authoritative co-op bag confusion and remote roster mirrors.
- Restored early voluntary roster handshake; decode global stages only at
  native engine ingress, preserving tagged rotations/cancellation.
- Ball selection no longer spends before ordered execution; co-op excludes
  the unsupported last-ball shortcut. Catch validation uses the native ball
  enum rather than the legacy Master Ball numeric lower bound.
- Mandatory native builds passed through29. Actual build27 shared-win/private
  EXP/save/cold-Continue regression passed. Capture/full-six edge acceptance
  and build29 complete-bundle acceptance remain pending.
- Presentation/summary/reshow closure is delegated from complete source review.
  Strict-dispatch draft is HELD: independent review found legitimate-action
  rejection, missing completion, premature correlation retirement and missing
  snapshot implementations. It is not integrated or accepted.

## Final RC7 pre-RC9 checkpoint

Engine 9506377d1fff0e1f553caaf66f99550cbd715f59 includes original menu-return, absent-NPC rendering, trainer presentation and private-summary guards. The actual extracted Linux package passed ordinary multiplayer battle, shared wild win/private EXP, independent normal saves and cold Continue. Packaged DesktopSession created and authenticated an Expansion profile and reached ready overworld. No separate RC7 release was published; user selected combined RC9 from this checkpoint plus Dot PR237. Capture/medicine are expected implemented behavior, not disabled features; their complete action journey is not asserted here.


## DexNav collecting UI source candidate

`native-collecting-ui.patch` applies after the four patches listed in
`player-ui-source-manifest.json`. `collecting-ui-source-manifest.json` records
its exact base/result trees and file hashes. The released engine gitlink is
unchanged. Integrate this source into trusted engine ancestry and rebuild with
all mandatory native checks before including it in a player package.

In Expansion DexNav, L selects the next seen-but-uncaught species from the
screen's existing map encounters. It skips empty, unseen and locked hidden
slots. It does not start searching, register a species, reveal unknown names,
change encounters or write a save. A still searches and R still registers.
The native header keeps registration on the left and exposes L Uncaught on
the right in place of the map name. If no eligible species exists, selection
stays put and the header says No known uncaught. WORLD explains each actual
DexNav restriction, including generated-area wildlife, rather than showing a
single generic error. No gameplay option or default is changed.

Run `python3 -m unittest test.world.test_dexnav_collection_ui -v` for the
source-candidate fixture. Set `EW_RC7_ENGINE` to the applied Expansion checkout
to verify exact file/function correspondence as well. The fixture executes the
actual DexNav getter, input handler, navigation and availability code with
instrumented backends. It covers all cursor slots, seen/caught states, detector
locking, form-to-national-dex matching and existing A/R/B input. It compiles
with warnings as errors and UBSan using installed compilers. It is not a
native game, screenshot or multiplayer acceptance test. Full native build,
rendering and gameplay remain unverified.
