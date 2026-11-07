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
