# Experimental owned-furniture floorplan guidance

Independent native child of #81, a8355423fcd4ba90a6668b4d230134da5325354e. Not Maya #72 or released RC12. WORLD_FLOORPLANS defaults off.

An authored plan is public metadata for one of 24 stock Secret Base room layouts, with 1..16 ordered [decoration,x,y] suggestions. The catalog names 120 existing decorations; no assets or new furniture are imported. Coordinates are native bottom-left anchors. Bounds checks are not proof a floor/surface supports the design. Native placement may refuse it.

## Real player workflow

1. Browse /guild floorplans [page] (pages start at 0). Enter your own matching Secret Base through ordinary gameplay.
2. In idle field play use /floorplan ID. This downloads guidance, not inventory or a base. It sends only the public plan ID and request sequence, never furniture, room layout, party or placement results.
3. The existing native chat panel shows the next missing decoration and target anchor. Open your base PC normally and select that decoration from your actual owned inventory. The plan does NOT select or grant furniture.
4. In the stock placement cursor, press the game's SELECT button to guide it toward the suggested anchor. Movement uses the existing cursor, camera, sprite timing and boundary checks, not a teleport or synthetic world movement. D-pad interrupts; SELECT toggles guidance. A/B stop guidance and retain their ordinary behavior.
5. Press A and confirm the stock placement prompt. Existing unused-inventory, capacity, surface, collision and sprite/script rules decide whether placement is possible. A suggestion never presses A/Yes or bypasses a refusal. Choose another location freely if you prefer; that does not satisfy the suggested anchor.
6. The panel reads the next missing item/position from the actual base arrays. Existing matching furniture counts as present, not as a claimed new placement. Select each next item at the ordinary PC. /floorplan stop removes guidance; it does not undo placements.

The helper is disabled for visitor bases, player bedrooms, put-away mode, a different trainer/base/layout and native link battles. Stock menu behavior remains the default. It does not create a new native floorplan picker or auto-select inventory. Missing/unowned/in-use furniture is still rejected by the ordinary PC UI; players must obtain furniture normally.

## Consent, privacy and recovery

No base array writes, inventory transfers, remote saves, placement reports or automatic neighborhood publication are introduced. Existing neighborhood publication remains a separate explicit opt-in after the player chooses to share.

The downloaded immutable plan is frozen locally. Closing its public listing prevents later downloads, not already-loaded guidance. Disconnect stops a pending request and cursor guide, retaining read-only loaded guidance. Download timeout is 600 native transport pumps; stale/duplicate responses cannot replace a plan.

Cancel keeps completed in-memory native placements. Save normally to persist them. Restart does NOT preserve unsaved edits: it follows stock save behavior. Reloading the same plan after restart derives progress from actual saved decorations, with no hidden completion flags, automatic retries or resumed placement commands. A different save cannot use the previous trainer/base binding. No atomic multi-placement transaction is claimed.

## Verification limits

Two component tests compile actual new C protocol/progress/direction functions with feature off/on and test request parsing, missing-step detection, no placement mutation, SELECT/manual interruption, shape bounds, wrong furniture/mode, stale owner/base, timeout, cancellation, duplicate rejection and reload from actual fixture arrays. Source checks cover stock inventory/confirmation/placement and independent transport/UI wiring. The stock inventory-use, CanPlaceDecoration and write/confirmation functions were compared byte-for-byte to #81 and remain unchanged.

This is not a full linked build or rendered decoration test. Camera/cursor timing, SELECT/controller mappings, wrong-floor refusals, sprite dolls, layered furniture, existing/in-use inventory, cancellation at every stock prompt, actual disk save/reload and ordinary room/base regression QA remain pending. Keep disabled until verified. No live providers.

## Agent authoring and app ancestry

App follows #430 at 93645d4c8fd6ae6734cb48e6a483b8a621090d5f, not Maya #410. world.publish_floorplan(id,design) accepts JSON {title,layout,placements:[[decoration_id,x,y],...]}. Discovery exposes exact layout dimensions and native decoration footprints/permissions. Design identities are immutable and owned by their author. Empty design closes a listing; the same exact design can be reopened. At most 16 active designs per author and 128 globally; closing frees active capacity without discarding history. This is no claim of a player's construction or possession.

Use --development --experimental-floorplans for paired development QA; ordinary builds pass WORLD_FLOORPLANS=0. Authority tests cover an actual author plan/receipt, authenticated public download, durable catalog, bounds, identity/ownership, closing/reopening, transaction rollback, layered suggestions, and absence of private inventory or completion reports. No linked/native rendered QA is inferred.

Paired native draft #82: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/82 at 31b800a1376d68e6361e8c22a7ee0778f3adf897.
