# Living route rematches in original Match Call

This connects an existing authorable rematch opportunity to Emerald's actual PokéNav, original trainers and native battle progression. It does not add a second event engine, trainer roster, quest or battle reward.

## Experience

An independently running character/world author can use `world.organize_rematches` for a reviewed Hoenn route and bounded duration. No event is installed by default and no provider is started. During an event, eligible original trainers become available through their ordinary interactions. Each save must already have defeated and registered the trainer and meet native badge requirements; forbidden/special trainers, Gym leaders, Wally and VS Seeker charging paths remain excluded. Teams, battle execution, earned rewards, rematch advancement and saves remain native.

With the new experimental flag, the original Match Call list can show the ordinary readiness icon for these eligible trainers even when their route is elsewhere in Hoenn. Nearby-rematch indicator, nearby-message decision and rematch call text use the same temporary eligibility query. The original call-text availability/plot prerequisites still run first. When its existing rematch-text section has been reached, an actually available event can select the stock rematch invitation without writing the game-clear flag. Kanto/standalone FireRed do not get temporary Hoenn readiness.

Players discover an opportunity, call a registered trainer, travel normally and choose the original battle. A ready icon is not a reserved encounter or a promise that an expired event persists. Nobody is warped, automatically enrolled in a battle, awarded someone else's progress or given a new trainer identity. Characters author temporary availability; this is not proof that those route trainers independently negotiated attendance or trained new Pokémon.

## Reconciliation and lifecycle

Exact app #488 did not contain the earlier `route_rematch_events.py`, its runtime capability or J transport handler, although native #126 retained that feature's cache and battle hooks. This draft restores the existing authority capability and optional `/guild rematches` listing, then wires the new original-game discovery path. It is not advertised as a second rematch system.

Legacy `J GET 1` still returns only the current route. Experimental `J GET 2` returns one complete bounded snapshot containing up to 26 reviewed routes. Each entry carries map group/number and at most 30 seconds of remaining lifetime. A native parser stages the entire list, rejects malformed/duplicate/oversized entries, then swaps it atomically. NONE, malformed input, expiry and existing disconnect reset remove temporary readiness. Polling remains every 300 link pumps. Pausing the client pauses its pump clock; closure may take the polling interval or remaining lease to become visible. Existing cached PokéNav graphics can require redraw/reopening after a change. The actual call/battle eligibility query always rechecks current cached state; it never persists an icon as readiness.

Native battle entry still requires the actual trainer route. Only the UI can query another route. All original saved readiness is ORed with eligible temporary readiness and is never cleared by event shutdown. Special/Gym/Wally readiness and native progression remain unchanged. There are no save-layout changes or real-save tests.

`EW_MATCH_CALL_EVENTS=0` is the default. Enable new multi-route/PokéNav behavior only with `--development --experimental-match-call-events`. The restored pre-existing current-route author capability can still serve legacy clients; with no authored event ordinary gameplay is unchanged. This flag is not a claim that the legacy feature has been removed or globally disabled.

## Verification

Four focused tests pass: actual authority configure/ownership and GET1/GET2 snapshots, expiry and SQLite restart; actual authenticated server link-handler dispatch and stale presence rejection; compiled actual native cache plus extracted actual eligibility functions with UBSan in both flag modes, covering remote UI vs local battle admission, registration/defeat/badges/forbidden/VS Seeker/Kanto/special exclusions, malformed and duplicate snapshots, expiry and reset; and all affected PokéNav saved-readiness consumer checks. Python compilation passes.

These fixtures do not run an original trainer script, actual PokéNav renderer or linked battle. Full native syntax/build is blocked in the recovered checkout by missing inherited header declarations and generated COMPOUND_STRING/INCGFX inputs. Full exact-head linking, menu refresh/pacing, native calls, original rewards, two-client play and save/reload remain unverified. No live providers or actual saves were used.

Separate stack on app #488 `5adfa7765cd769b011f5c957e74b26334efe73ab` / native #126 `bcb77ed4c13a6b937de4a4169b15bea8c81c3c05`. Maya's #410/#72 and all held operations are untouched. Maya owns integration and release.

Paired native draft #127: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/127 at `0a337e13b1d9e1103f27209a3f7a954b1901a144`. Focused test command: `python3 -m unittest discover -s test -p test_match_call_events.py -v`.
