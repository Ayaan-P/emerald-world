# Kanto content on RC10

This draft follows main at RC10 `3d336831f06672c93ea3e4402f95aba4dd0b55b6` and pins published native Kanto commit `e2aa70213d1176763b154bb338da18d97afa595b` (tree `8eedfe361c12dc2af6ca2b98911b17658bfb118b`, parent `c8feb78cfb7bdd82c19406eabe0f36716ea87f16`). The engine includes Expansion 1.17.2. Maya's integration branch, app main and the earlier PR239 are unchanged. The old RC9 overlay remains historical; do not apply it to this engine.

The opt-in combined generator retains Hoenn, upstream FireRed/LeafGreen maps and generated-world maps. The content cohort now selects both regions' event scripts and tileset declarations. The entire combined event-script object assembles with the actual upstream preprocessor and native assembly filter. The filter handles spaced comparison expressions without editing game dialogue. Script macros recognize the regional variable bank when selecting variable comparisons and validating copy operations.

## Actual story-entry integration

The existing `RunOnTransitionMapScript` now initializes a Kanto map's story state once, before that map's own callback. It executes Expansion's existing FireRed defaults, records initialization in the trainer's regional bank and leaves subsequent entries alone. A shared-name exception is explicit: the Kanto initializer hides Kanto's Deoxys without setting Hoenn's `FLAG_HIDE_DEOXYS`.

The bank now maps 211 named FireRed persistent variables and 762 named FireRed flags by their original upstream identifiers. It does not reinterpret Hoenn IDs by their numerical value. Existing Emerald definitions, temporary/special registers and system flags such as Dex, badges and game-clear remain shared. This is not full story isolation: duplicate names outside the initializer and some runtime helpers still need region-aware integration.

Host integration tests compile the actual script interpreter, script command handlers, event accessors, game save/load hooks and native flash driver. They execute the upstream initialization and Pallet transition bytecode, exercise the sign-lady scene, compare regional variables, save and cold-load both trainers, and prove the tested paths leave SaveBlock1 unchanged. Map preview and object-display adapters are substituted in this test; it does not render or walk the maps.

## Trainer battle integration

All 623 nonzero named FireRed trainers now have disjoint runtime IDs at `0x2000 + original ID`. Zero still means no trainer. The range stays below the script variable boundary, so the existing `VarGet`-based trainer commands accept both literal IDs and variables containing IDs. Hoenn trainer counts, partner IDs, special opponents and saved structures do not expand.

The combined cohort generates a compact second table from the unchanged upstream `trainers_frlg.party` using Expansion's trainer processor. The processor permits an index mapping on table designators only, so party references such as `overrideTrainer` retain their runtime IDs. Existing battle accessors select the correct table for parties, names, classes, music and difficulty fallback. Multi-team sizing and slide lookups no longer index a Hoenn array with a Kanto ID. The default cohort preserves the original paths.

Actual trainer argument loading, script check/set/clear commands and battle-result defeat hooks now address Kanto's regional flags. Tests compile both complete upstream trainer tables, resolve every Kanto ID, load Viridian Forest's original Rick bytecode, exercise literal and variable command operands, verify Hoenn state is unchanged and cold-load two independent trainer profiles. The real encounter-music and multi-party lookup functions and slide source are exercised under ASan/UBSan. The full battle renderer and battle loop are not run.

The combined-script assembly test exposed one upstream Rocket Hideout call whose arguments lacked a comma. The native content branch supplies the separator without changing dialogue or the default script path. Kanto co-op credit remains rejected by the existing native bounds checks. Rematches and region-specific battle/story helpers are not fully wired.

## Encounter tables and travel backend

The upstream encounter generator now selects FireRed data alongside Emerald in the experimental content cohort. LeafGreen remains a separate variant. A compiled test compares every generated species, level range and encounter rate with the standalone-region outputs, and executes the actual map-to-encounter lookup for Route 101, Route 1, Viridian Forest and an unknown map. Encounter generation and a complete wild battle are not exercised.

The optional layout-aware safety catalog records each map's primary/secondary boundary and attribute width. All 520 existing Hoenn entries retain their allocations. The enabled native catalog adds 417 FireRed-layout entries, using the upstream 640-metatile primary boundary and 32-bit attributes. The default Python/server catalog and its generated header remain byte-identical. The shared travel safety path now uses Expansion's existing layout/attribute helpers after checking the recorded allocations. Its behavior value remains wide enough to reject FireRed's 9-bit non-floor behaviors.

A route table connects Slateport's normal landing at 19,20 and Pallet's normal landing at 6,8 through the existing checked warp backend. This is a local backend checkpoint, not an exposed travel menu. The WORLD-menu hook is deliberately excluded while the launcher/UI is being redesigned. The only launcher change carried here is the already reviewed opaque save-import size bound from PR255; no travel UI is added.

Route admission checks the trainer's own Slateport visit flag, compatible regional state, an able party, walking state and available field/task ownership. Active rallies, scripts, links and busy fields block travel. It also blocks connected world sessions because the current server catalog cannot admit Kanto map IDs. Future server/cohort integration must be explicit. No shared world admission or story state is forged.

Tests use the real map and tileset bytes and production travel functions. They check doors, story triggers, bounds, format mismatches, unavailable tasks, both directions, repeated requests and unchanged story state. The final warp-animation call and field/UI status adapters are substituted; rendering, actual map loading, menu input and gameplay remain unverified. The normal save location is used, with no transient return anchor or second save format.

To regenerate the native catalog, use `build_catalog(engine_path, layout_aware=True)` and `render_layout_header` from `world/build_catalog.py`. The v1 generator behavior remains unchanged for the existing server.

## Native save compatibility

SaveBlock1 and SaveBlock3 retain their layouts, measured at 15,768 and 1,574 bytes. The regional bank supports 256 variables and 4,096 flags. The versioned extension allows up to 8 KiB per normal save slot in the same atomic native save file, with exact save-counter matching and fallback recovery. There is no second save file or service.

Legacy profiles keep the original v1 format until the optional extension is used. Regional saves use `PENSAV2`, preserve the original flash image and append a length/CRC-protected payload. Legacy saves start with empty regional state. Old readers and the disabled cohort refuse regional saves without overwriting them. Malformed versions, lengths, CRCs, schemas and counters fail closed. Normal, interrupted/complete link saves and actual older-slot recovery are covered by the inherited host tests. Profile init/load/shutdown reset working state.

## Build and test scope

Use the real pinned repository and instructions in `port/kanto-on-rc10/README.md`. `--development --regional-state --kanto-content` selects the experimental cohort. Ancestry, Bubblewrap isolation and mandatory native ABI checks remain in force. Species export now runs after a successful guarded build because it requires generated headers. A failed build leaves the app catalogue and published binary untouched. Both experimental switches remain off by default.

Run the focused tests with:

```
ASAN_OPTIONS=detect_leaks=0 EW_RC7_ENGINE=/path/to/patched-engine PYTHONPATH=.:test/world python3 -m unittest test.test_rc9_kanto_encounters.KantoEncounters test.test_audit_region_state test.test_rc7_combined_regions test.test_rc10_region_identity test.test_rc10_kanto_cohort -q
```

`EW_RC7_ENGINE` is the existing test-source selector; here it points to the exact published RC10 Kanto source. The sanitizer flag is needed only where LeakSanitizer cannot run under tracing. ASan and UBSan remain active. The native extension/save-file/store/lock suites are additional regressions.

This is **not playable Kanto**. No travel menu or region transition is exposed. Trainer data and defeat-state routing are integrated, but this has not been tested through a complete in-game battle. Some shared-name story state, special registers, rematches and runtime helpers still need review. Combined encounter data and the local route backend are now tested, but connected-world admission, the UI handoff and a full regional journey remain unfinished. The full game has not linked or run with this patch. Graphics declarations were checked, not rendered. Full native checks, headless gameplay, GBA ROM neutrality, 32-bit/Windows and combined multiplayer are unverified. The exact published Git objects and official upstream history now allow the ancestry gate to pass locally. No check was bypassed. Use disposable profiles only.

## Explicit region identity and future imports

The real transition hook uses generated `WorldRegion_ForMap` metadata, not a graphics-layout flag or a numerical map range. The generator recognizes explicit HOENN, KANTO, JOHTO, SINNOH and CUSTOM identities. Tests compile and execute the generated lookup, deliberately reverse graphics labels, and verify appended regions preserve prior IDs. Unknown identities, duplicate IDs and values beyond the existing signed 8-bit save map coordinates fail closed.

The current registry has 76 groups: GeneratedWorld remains group 34 and the upstream FRLG groups occupy 35..75. Future imports must append groups and set explicit `region` metadata. Recognizing a namespace does not import its maps, assets, scripts, trainers or story. No Johto/Sinnoh donor assets are added by this draft, and existing asset licenses and attribution obligations remain unchanged.

## Save backup and import

This branch incorporates the exact opaque-copy fix from app PR255. Native v1 saves include a 28-byte header beyond the 128 KiB flash image. Maximum PENSAV2 size is 147,524 bytes, including two bounded extension snapshots. Backup, base64/HTTP staging and the existing file picker use the engine-specific bound without truncating or converting data. Vanilla remains capped at 128 KiB. A compiled check compares the Python limit with the actual native headers. Native version/CRC/ABI validation remains the loader's responsibility.

## Verification for this source checkpoint

Fresh checks on the exact published engine tree:

- 53 Python/compiled-C component cases passed for regional state, scripts, trainer lookup/defeat, encounter tables, route safety, explicit namespace identity and existing generated-world regressions.
- 74 native C extension/save-file/store/lock cases passed.
- Trainerbattle serialization passed all 9 32-bit/GBA and 64-bit variants, all 8 pointers and both loaders.
- 3 map-storage checks passed against the selected source.
- 17 additional tests passed: 2 cohort/source-hash and copy-bound checks, 3 wrapper-order regressions and 12 backend copy tests. These cover byte preservation, bounds and existing private-file safeguards.
- All 6 Node tests and 131 launcher UI tests passed; the production bundle built with existing dependencies.
- The same SDK inputs already present in the environment were reused. No packages were installed.

The guarded full build now passes source/ancestry checks but stops before compilation because Bubblewrap's network-namespace setup cannot create a NETLINK_ROUTE socket in this environment. No isolation or socket restriction was bypassed. Aggregate native ABI checks, a complete linked game, graphics, real battle loops, rendered travel, 32-bit Windows, GBA neutrality and connected Kanto remain unverified. No game, service, deployment or human save was used.
