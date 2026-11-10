# Existing Kanto shared presence, experimental

The engine already contains Kanto, regional private save banks and a 937-map combined native catalog. The authority previously knew only 520 Hoenn maps and rejected Pallet STATE coordinates. This slice closes that presence mismatch. It does not import Kanto, Johto or donor assets, complete the Kanto story, add transport NPCs, or authorize arbitrary Kanto terrain changes.

## Explicit cohort

Use a **new** authority state directory:

```
python -m world.server --state-dir /path/to/new-combined-world --combined-regions --create-identity Alice
python -m world.server --state-dir /path/to/new-combined-world --combined-regions
```

Use the existing secure connection/identity workflow; never publish token output. Build the paired native pin with:

```
python scripts/build_expansion.py --development --regional-state --kanto-content --experimental-combined-presence
```

All players need this matching combined client. Default builds and default authorities remain Hoenn. The world database durably binds to its profile and exact catalog digest: neither silent downgrade nor implicit upgrade of an existing Hoenn world is allowed. This is independent of personal native region saves. No save conversion or cross-player progression is performed. Use disposable QA saves until linked testing completes. Existing launcher UI does not expose this experimental cohort; the standalone authority command above is the supported entry.

The native client's already authenticated separate LINK connection declares `RGC 1 DIGEST`, bound to its exact current presence object. Before that declaration, combined-world presence and player commands are not admitted and snapshots are empty. Missing proof expires after five seconds; wrong declarations close both channels. Loss of LINK revokes the corresponding presence, and reconnect requires new negotiation. CONTROL/admin access does not impersonate presence. This is client-declared protocol compatibility, not remote binary attestation.

## Actual scope

Matching clients can report real map 38/0 (Pallet) positions, see ordinary peer snapshots and return to map 0/1 (Slateport), using the existing native map renderer. All 937 registered map bounds are checked. The registry retains per-map primary/secondary allocations and attribute width; its separate tile validator handles Emerald's 512 split and FRLG's 640 split rather than reinterpreting metatiles.

Authoring, guild destinations, campaign visits, content modification and other map-specific gameplay catalogs remain their existing reviewed Hoenn/generated-map scope. The combined tile helper is validated but is NOT wired as permission to edit arbitrary Kanto terrain. This is a presence cohort, not full cross-region gameplay parity. Stock private Kanto gameplay remains the native engine's responsibility; this patch does not validate a complete Kanto adventure or route to get there.

The metadata is derived only from the user's native #82 source: `include/platform/world_catalog.h` plus `data/maps/map_groups.json`. All 520 baseline records match. The additional 417 are existing gated FRLG maps. No external donor artwork, maps or scripts copied. The metadata's source commit remains recorded even when the native pin advances for the handshake-only change.

## Verification

- Six catalog/profile and actual WorldServer wire-handler tests pass, covering Pallet peer snapshots, Hoenn return, bounds, private client hash preservation, 512/640 allocation limits, matching proof, bad/missing proof, timeout, stale/reconnected LINK, default Hoenn and persisted profile mismatch. Handler tests use a fake selector/socket boundary, not real OS sockets.
- Existing campaign, actor runtime, link coordinator and build setup tests pass. Build setup is mocked, not a native build.
- Two native announcement/header tests pass, including compile-time prerequisites and actual welcome hook placement.
- Real Unix-socket tests are preserved in `test/manual/test_combined_region_sockets.py`. Seven socket-using tests could not run here: socket(AF_UNIX) returns Operation not permitted, including after an authorized escalation. Two non-socket checks in that suite passed. No bypass was used.

Full linked native build, actual socket handshake timing, rendered two-client Pallet/Hoenn transitions, and cold private-region save QA remain pending. No live provider calls. Separate child of app #432; not Maya #410/#72 or RC12.

Paired native draft: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/83 at `40f9efdc8dcb705e270647f452925e31bfa28715`. App parent #432 is `ad4b20a2444852988c57976f4425261c54f93515`.
