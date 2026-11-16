# Connected regional ports: authority pairing

App parent #433: 649df6fcb6907c2f8cb173214f174db37db4122e.
Native paired #84: 659eb2ae1fd66dc6be9b0c733a8850b9b3b40c74.
This independent stack does not reconcile Maya #410/#72 or RC12.

Build with --development --regional-state --kanto-content --experimental-combined-presence.
Start the matching authority with --combined-regions on its existing combined-profile world
(or a new world); no automatic Hoenn-profile migration. WORLD now enables the existing
regional-port action only after a version-2 current-session ACK. Legacy version-1
combined clients retain presence-only behavior. Local personal eligibility remains native-owned.

38 authority/build regression checks and four native checks pass. Authority tests use
real handlers with mock sockets, not live socket transport.

# Connected Slateport / Pallet travel (experimental)

Parent: native #83, 40f9efdc8dcb705e270647f452925e31bfa28715.
Uses the existing regional route and WORLD menu. No donor assets, save-layout
changes, story flag grants, new travel scripts or bridge changes.

With WORLD_COMBINED_PRESENCE enabled, LINK now declares RGC 2 and waits for an
exact RGC OK 2 registry digest. Disconnect clears that admission. Existing
RGC 1 clients retain presence-only compatibility on the paired authority.
Older authorities reject version 2 rather than enabling unnegotiated travel.

At Slateport or Pallet choose Travel to Kanto / Hoenn in WORLD. Each choice
rechecks personal Slateport visitation, regional-state availability, conscious
non-Egg party, on-foot idle field, no rally return and no active/pending LINK
activity. Connected travel additionally requires current bridge connection and
the matching LINK ACK. Default builds and offline routes retain existing behavior.
Normal native landing validation and SetWarpDestination / DoWarp execute the
trip. Online landings use the existing available-peer occupancy check too.

This is personal normal warp travel, not a shared progression transaction:
no rewards, items or story flags are granted, no group is moved, no automatic
save occurs. Save normally after arrival; restart uses the last normal save.
A disconnect after native warp starts does not roll it back or replay it.
Each participant chooses separately. Existing regional save recovery owns
personal Kanto progression. No full Kanto campaign is promised.

The existing peer cache is not an exclusive destination reservation. Another
player can arrive simultaneously, as with ordinary multiplayer map movement.
Do not describe this as atomic collision-free group travel. Native map/events
and the player's current state remain checked immediately before warp.

Verification: four focused native tests, including compiled actual route code
with engine boundary stubs and header checks. Authority handler tests cover
version negotiation, Pallet/Slateport reports and stale-link reconnect.
No full engine build, rendered UI, linked two-client play or disk save/reload
test performed; disposable-save QA required before integration/release.
