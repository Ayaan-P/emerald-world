# Move-driven reconnaissance

Independent app child of #418 (`98e6d30fb4caac2172eaa6cd5d94ce4441944988`), paired native #78 `9de771be6b41eaaa61356e3c5c272b6b0bcf1fda` (child of #77). Not Maya #410/#72 or RC12. No denied/uncertain operations touched.

## Authoring and player flow

`world.configure_move_sensing` is discovered in the general actor runtime, with move_sensing.maps/profiles. Actors select a reviewed route, existing move-selector JSON, radius 1..5 and PP cost 1..4. Profiles persist and are actor-owned. A configuration receipt is not a discovery, scan, collection or NPC knowledge. No preset moves or puzzles are installed.

In the default-off matched build (`--development --experimental-field-moves`), choose an actual learned party WORLD MOVE. Request a sensing profile only after the menu disclosure that the chosen move ID goes to the world host. Lookup spends nothing. Explicitly choose scan after seeing radius and PP cost; default is other interactions. Native requires Itemfinder possession, actual learned move, conscious non-egg source, current PP, unchanged owner/map/source/position and safe ordinary field context.

A valid scan spends PP even if nothing is found. Pure native query reads current-map hidden-item events and the player's actual collection flags. It returns the nearest uncollected tile, not item identity or guaranteed accessibility. No item/collection flag changes or shared inventory. Stock Itemfinder reuses the pure query for its current-map pass, preserving connected-map scan and nearest/tie behavior; move sensing is current-map only. Cry feedback, no bespoke sensing animation.

Results are private by default. A separate explicit choice sends a clue to nearby opted-in world players using existing eight-second look markers. The sender label says reported clue. It is a client report about the sender's personal save, not verified native proof, a shared-world item or proof another player can collect it. There is no public history or inferred NPC knowledge. Sequence/move/location/radius/deadline-bound offers are one-use; movement, expiry, duplicate and out-of-range reports reject. No automatic sharing retry.

Normal manual save semantics retain PP expenditure. No forced save or redelivery receipt. Native disallows generated maps, Safari, facilities, Battle Tent rooms, Trainer Hill, battles/link, scripts and fades. Existing independent call/care/object/profile actions remain available without sensing lookup.

## Verification

Nine native compiled-source/component tests pass, including actual pure query, activation and UI. App tests cover actual actor plan execution, persistence/ownership, fresh authenticated lookup, no marker before sharing, replay/range/movement rejection and existing runtime/move regressions. Full linked native build, rendered Itemfinder/dowsing/move UX, save/load and multiplayer QA remain pending. No live providers. Draft, not release-ready.
