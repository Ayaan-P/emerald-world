# Kanto multiregion: source preparation

This draft adds an opt-in `combined` mode to the existing map generator. It consumes the Expansion source's FireRed/LeafGreen maps alongside Emerald and retains RC7's generated-world maps. Tests compile the real generator and verify Hoenn, Pallet Town, generated maps, and Pallet's actual event and connection metadata. The default Emerald mode remains unchanged.

This is **not a playable Kanto port**. It does not wire a region transition, import and validate all scripts and assets, isolate progression, or establish a native build or multiplayer behavior. Do not enable it for a release. Map metadata generation alone does not establish that the combined game links or runs.

Progress isolation is a concrete next step: FireRed and Emerald reuse variable IDs, while many FireRed flags are defined as zero placeholders in the Emerald constants. `scripts/audit_region_state.py --engine PATH` reports direct variable aliases and placeholder flags referenced by FireRed map scripts. It is a static audit and is neither a reachability analysis nor an exhaustive inventory of all scripts, state or assets. Any solution must preserve each trainer's independent progression, party and inventory.

Run focused source checks with `EW_RC7_ENGINE=/path/to/patched-engine PYTHONPATH=.:test/world python3 -m unittest test.test_audit_region_state test.test_rc7_combined_regions -q`. This requires a C++ compiler and the actual source tree, but no server connection.
