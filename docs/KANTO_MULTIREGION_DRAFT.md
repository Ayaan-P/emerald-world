# Kanto multiregion: source preparation

This draft adds an opt-in `combined` mode to the existing map generator. It consumes the Expansion source's FireRed/LeafGreen maps alongside Emerald and retains RC7's generated-world maps. Tests compile the real generator and verify Hoenn, Pallet Town, generated maps, and Pallet's actual event and connection metadata. The default Emerald mode remains unchanged.

This is **not a playable Kanto port**. It does not wire a region transition, import and validate all scripts and assets, isolate all Kanto progression, or establish a native build or multiplayer behavior. Do not enable it for a release. Map metadata generation and host-level save tests do not establish that the combined game links or runs.

FireRed and Emerald reuse variable IDs, while many FireRed flags are defined as zero placeholders in the Emerald constants. `scripts/audit_region_state.py --engine PATH` reports default-cohort variable aliases and placeholder flags referenced by FireRed map scripts, including the optional regional wrappers. It is a static audit and is neither a reachability analysis nor an exhaustive inventory of all scripts, state or assets.

## Opt-in regional progression and native save extension

`EW_REGION_STATE=1` routes five named Pallet scene variables and seven Pallet object/story flags through Expansion's existing `GetVarPointer`/`GetFlagPointer` accessors into a separate native bank. It does not reinterpret overlapping Hoenn IDs by their numeric value. Dex, badges, game-clear and other shared system flags keep their existing SaveBlock1 storage. All other Kanto script-state mappings and the story's initialization still need integration.

The bank has 256 variables and 4,096 flags, enough for the original Kanto ID ranges. Its portable, versioned payload uses the existing native save file's atomic write/replace path. There is no second save file or network service. The reusable extension accepts up to 8 KiB per normal save slot, with explicit payload schemas and exact save-counter matching. The actual normal and link save paths capture only after the first save sector writes successfully. The normal load path restores the counter chosen by the existing slot-recovery logic. New-game initialization clears working progression; profile init/load/shutdown prevent cross-trainer state reuse.

SaveBlock1 and SaveBlock3 are unchanged. A compiled size probe reports 15,768 and 1,574 bytes respectively; SaveBlock3 has only 50 bytes free in this cohort. Ordinary profiles remain byte-format v1. The optional extension uses `PENSAV2` magic and version 2, preserves the entire original flash image and adds a length/CRC-protected extension. Legacy v1 profiles start with empty regional state. The original v1 reader and the new feature-disabled cohort both refuse regional saves without overwriting them. Bad versions, lengths, CRCs, schemas or counter matches fail closed. Use disposable profiles: no full game migration/replay has been accepted.

The normal build wrapper exposes `--development --regional-state` and still requires its trusted ancestry and mandatory native checks. It has not been bypassed. Map generation and regional-state storage are separate experimental switches; neither enables a complete Kanto game.

Focused integration checks: `EW_RC7_ENGINE=/path/to/patched-engine PYTHONPATH=.:test/world python3 -m unittest test.test_rc7_region_state -q`. This compiles actual `src/save.c`, `src/event_data.c`, native flash and persistence code with ASan/UBSan and generated real headers. It exercises normal save/cold load, unsaved edits, failed saves, interrupted and completed link updates, actual older-slot recovery, two independent trainer profiles, counter mismatch, new-game reset, unchanged save sizes and shared flags, and disabled-cohort refusal. It does not run map scripts, the renderer, a full game or multiplayer. LeakSanitizer is unavailable under the current traced sandbox; only there, run with `ASAN_OPTIONS=detect_leaks=0` and report that limit.

Standalone platform tests include `test_save_extension` and `test_save_extension_file`, alongside the existing save-file/store/lock suites. The mandatory full native build, headless gameplay, 32-bit/Windows checks and real combined multiplayer remain unrun.

Run focused source checks with `EW_RC7_ENGINE=/path/to/patched-engine PYTHONPATH=.:test/world python3 -m unittest test.test_audit_region_state test.test_rc7_combined_regions -q`. This requires a C++ compiler and the actual source tree, but no server connection.
