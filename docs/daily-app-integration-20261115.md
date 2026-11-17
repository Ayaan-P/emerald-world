# November 15 frozen Dot app source integration

Status: source integrated, focused tests complete; independent review and the parent's exact-pair build/package/gameplay acceptance remain separate gates. This document does not assert a verified release.

Baseline: `a27bb4e724e51ec88ba736512a59ae1e38951787`.
Frozen inventory: `/home/ayaan/emerald-daily-20261115/inventory.json`.
Machine-readable dispositions, commands, baseline RED and merged GREEN results:
`/home/ayaan/emerald-daily-20261115/app-integration.json`.
Evidence logs and saved actual patches: `/home/ayaan/emerald-daily-20261115/evidence/`.

## Delivered source

- Generated connected adventures combine named distinct layouts, authored or composed Expansion habitat tables, reachable entrance/exit-anchored residents, optional mechanisms and optional independent campaigns. Existing admission, ownership, resume and explicit player choice remain.
- Shared CAVE17 landscapes gain deterministic biome palettes, safely bounded ponds, walkable marked trails, and routes connecting generated clearings. No new artwork, surfing, movement authority or personal-save mutation is introduced.
- The area library finds painted outdoors and previews immutable archived terrain with palette/geometry validation and a schematic legend. The changed JSX is source only: no launcher bundle built here.
- Optional character-authored studies accept exact archived painted XL maps and validated terrain context. Private visits remain private; only explicit anonymous shares become public evidence.
- Persistent reactions support committed public TV reports, recurring/recent event thresholds, explicitly shared race finishes and explicit shared-research aggregate additions. Trigger substitution exposes only committed event IDs, not event text. Public research gap queries do not inspect personal Dex ownership.
- After race start, an individual leaving, disconnecting or losing movement/mount reports no longer stops other racers; unfinished runs never gain completion credit.

## Actual ancestry, not an adaptation-only claim

All **20** frozen new tips are actual ancestors. Cumulative heads supply compatible implementations; explicit three-way merges also preserve branch-only ancestry. The table is the frozen input, not moving refs.

| Dot head | Frozen SHA |
|---|---|
| adventure-resident-anchors | 5eb4d5753a4c42ff8b888c791ee8e78966a67e52 |
| coherent-generated-adventures | a6ab02589c1856e688a3e6712beaad8af98b03b3 |
| coherent-outdoor-atlas | e34ddc35c612ff477e16f384c935af80e21f3035 |
| coherent-reactive-world | ef7869fe097bb8078fe96a5c2d1c85c48cb99b07 |
| connected-adventure-habitats | 3286d8b866aaf0f9f5277bd6040c15f4e0712835 |
| history-triggered-tv-reports | 7f87aaaf1cfee5bedb196afba11506cf11a008f9 |
| independent-race-continuation | c240108625d9c73eda25a8fe2c90bba112cee10a |
| landscape-trails | 1e626a4d35408e5b8c34f85b778c86ef7b48fe97 |
| outdoor-landmark-networks | 591f09b50dc23c5b9cf3c8d31b5726460c39eb2b |
| painted-outdoor-field-studies | f1b10787f120fb472b394ed66d5a0840ef036cbd |
| painted-world-atlas | 2ac6000bb47312904435e06de645c383525dfae1 |
| recent-world-activity | 489a4bffd1f14dd53ed6bc358d8fa2c9e1efb74a |
| research-reactive-world | 3cc97d5dd88af0102891cd3e289b439f9bfedcfc |
| shared-biome-landscapes | 9b419de340d1a46df490aa5156d60142751d91db |
| shared-lakeside-landscapes | 6ab5f676f133e6c88261409cd0c10a3c4d59fceb |
| shared-race-world-reactions | 93e4a59686ee3ac615213e49bdceef611121eaf1 |
| shared-research-discovery | d8ecd6c8b3af7247adc5b2f58d265d0978f00bb8 |
| terrain-aware-study-authors | 32564f49b2f62408d4ac2d8ce02eb55ec69d7275 |
| varied-adventure-regions | 76d3443f83f92d4c7dec28e887c27e7e0954f804 |
| world-history-thresholds | 4d02a81d8396a51ee28ae6ac52edd8c0b0d717d3 |

Conflicts were overlapping cumulative/individual donor additions: preserve cumulative adventure capability descriptions and tests, landmark-network endpoint/protected-landmark extensions, generated-terrain archive-preview coverage, public research-gap assertions, and both adventure/study documentation sections. No released privacy repair was replaced wholesale. No head has a source-integration blocker; native/rendered acceptance remains pending for every applicable capability.

## Fail-first and verification evidence

Exact donor tests were overlaid on baseline without production changes, executed and restored before merges. The corrected baseline commands use `PYTHONPATH=.:test/world`; initial missing fixture-import attempts were harness errors, not feature proof. The outdoor donor's missing API imports are explicitly missing-feature evidence; other cohorts also reach real behavioral assertions. Baseline logs record all counts and reasons.

| Campaign | Observed result | Log |
|---|---|---|
| Merged feature cohorts | 84 tests PASS, zero skips | `merged-focused.log` |
| Prior preservation seams | 75 tests: 74 pass, 1 exact capability fixture failure | `preservation.log` |
| Capability fixture after four explicit additions | 5 actor-runtime tests PASS | `capability-fixture-green.log` |
| Daily source/Hoenn authority, identity, walks, canonical absence, combined regions | 33 tests PASS, zero skips | `protected-seams.log` |
| Launcher UI | 178 tests PASS, 23 files | `ui-green.log` |

The single integration adjustment updates the strict actor-runtime capability-set fixture for `world.create_biome_landscape`, `world.create_lakeside_landscape`, `world.create_trailed_landscape`, and `world.create_landscape_network`. It was changed only after the exact assertion failed. Strict equality remains; no production behavior was weakened to satisfy tests. No additional production-code repair was necessary.

Preservation includes mart witness/revocation, frozen shelf and queue/privacy cases, extracted production-native fixtures using the parent's standalone native worktree, generated geometry and consent scopes. Protected-seam coverage includes canonical identity nonce/revision, absence, walking and combined Hoenn/Kanto boundaries. These tests are not rendered gameplay acceptance.

A multi-cohort wrapper returned `pending_approval` and did not execute. Before parent steering arrived, a separate direct unittest invocation had already completed the merged campaign. The chronology is recorded, and that campaign was not subsequently reissued. Launcher locked dependencies were installed with `--ignore-scripts`; no assets built or services started.

## Scope and next gate

The source lane leaves the native gitlink, candidate manifest, build pin and three catalog provenance files identical to baseline. Parent owns their final exact-pair updates. No fetch, push, publish, install, human-save access, native modification, build, service or cron change occurred here.

Parent acceptance should create a new CAVE17 biome/pond/trail or clearing-network destination, inspect the saved palette, then actually walk routes around water/rock, visit an exact-revision optional study and explicitly share. For CAVE10 adventures, enter named varied habitats via normal REGION1/CAVELINKW1 admission, verify actual wildlife and reachable residents, decline optional challenges, and test ordinary outside-generated native Save/cold Continue plus unchanged authority archive re-entry. Independently demonstrate race continuation and public reaction opt-in. Full build, packaging, live native presentation and independent review must not be inferred from source tests.
