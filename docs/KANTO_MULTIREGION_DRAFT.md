# Kanto content on RC9

This is a Kanto-only draft on RC9 commit `73af5021705d67f65c9d5a9e510ba35d35a6902a`. It preserves the RC9 engine, launcher, co-op fixes and native map storage. It does not reapply the RC8 port or add PR238 world rules. PR239 remains unchanged as the earlier source preparation.

The opt-in combined generator retains Hoenn, upstream FireRed/LeafGreen maps and generated-world maps. The content cohort now selects both regions' event scripts and tileset declarations. The entire combined event-script object assembles with the actual upstream preprocessor and native assembly filter. The filter handles spaced comparison expressions without editing game dialogue. Script macros recognize the regional variable bank when selecting variable comparisons and validating copy operations.

## Actual story-entry integration

The existing `RunOnTransitionMapScript` now initializes a Kanto map's story state once, before that map's own callback. It executes Expansion's existing FireRed defaults, records initialization in the trainer's regional bank and leaves subsequent entries alone. A shared-name exception is explicit: the Kanto initializer hides Kanto's Deoxys without setting Hoenn's `FLAG_HIDE_DEOXYS`.

The bank now maps 211 named FireRed persistent variables and 762 named FireRed flags by their original upstream identifiers. It does not reinterpret Hoenn IDs by their numerical value. Existing Emerald definitions, temporary/special registers and system flags such as Dex, badges and game-clear remain shared. This is not full story isolation: duplicate names outside the initializer, trainer defeat flags, trainer parties and some runtime helpers still need region-aware integration.

Host integration tests compile the actual script interpreter, script command handlers, event accessors, game save/load hooks and native flash driver. They execute the upstream initialization and Pallet transition bytecode, exercise the sign-lady scene, compare regional variables, save and cold-load both trainers, and prove the tested paths leave SaveBlock1 unchanged. Map preview and object-display adapters are substituted in this test; it does not render or walk the maps.

## Native save compatibility

SaveBlock1 and SaveBlock3 retain their layouts, measured at 15,768 and 1,574 bytes. The regional bank supports 256 variables and 4,096 flags. The versioned extension allows up to 8 KiB per normal save slot in the same atomic native save file, with exact save-counter matching and fallback recovery. There is no second save file or service.

Legacy profiles keep the original v1 format until the optional extension is used. Regional saves use `PENSAV2`, preserve the original flash image and append a length/CRC-protected payload. Legacy saves start with empty regional state. Old readers and the disabled cohort refuse regional saves without overwriting them. Malformed versions, lengths, CRCs, schemas and counters fail closed. Normal, interrupted/complete link saves and actual older-slot recovery are covered by the inherited host tests. Profile init/load/shutdown reset working state.

## Build and test scope

Apply the source overlay as described in `port/kanto-on-rc9/README.md`. `--development --regional-state --kanto-content` selects the experimental content cohort through the existing build wrapper. The ancestry and mandatory native checks remain in force. Both experimental switches are off by default.

Run the focused tests with:

```
ASAN_OPTIONS=detect_leaks=0 EW_RC7_ENGINE=/path/to/patched-engine PYTHONPATH=.:test/world python3 -m unittest test.test_rc9_kanto_content test.test_audit_region_state test.test_rc7_combined_regions -q
```

`EW_RC7_ENGINE` is the existing test-source selector; here it points to reconstructed RC9. The sanitizer flag is needed only where LeakSanitizer cannot run under tracing. ASan and UBSan remain active. The native extension/save-file/store/lock suites are additional regressions.

This is **not playable Kanto**. No travel menu or region transition is exposed. The Emerald trainer table still interprets overlapping FireRed trainer IDs incorrectly, and trainer-defeat state has not been isolated. Some shared-name story state, special registers and runtime helpers also need review. The full game has not linked or run with this patch. Graphics declarations were checked, not rendered. Full native checks, headless gameplay, GBA ROM neutrality, 32-bit/Windows and combined multiplayer are unverified. The trusted engine ancestry cannot be recreated from source patches, and no ancestry check was bypassed. Use disposable profiles only.

## Verification for this source checkpoint

- 44 focused Python/compiled-C checks passed, plus 3 RC9 map-storage checks with the source path set to this reconstruction and 3 default-library checks.
- 74 native C extension/save-file/store/lock cases passed. The existing SDL runtime was used only for the unit-test link; no packages were installed.
- The original, unmodified RC9 v1 save reader was compiled separately. It refused the extended fixture and refused overwriting it; the file hash stayed unchanged.
- The Kanto overlay reapplies to the exact RC9 reconstructed tree. All 27 changed engine files match the tested source hashes in `port/kanto-on-rc9/source-manifest.json`.
- ASan/UBSan passed. LeakSanitizer was disabled because it cannot run under the traced sandbox.
- The broader RC9 browser tests require local Unix sockets and were blocked before creating a socket. They are not included in the passing count. No game server or deployment ran.
