# Shared field games on the combined region registry

Parent app #435: 0fcb075fad1c4f186171fd9b9b0720f654325301.
Native #84 pin unchanged: 659eb2ae1fd66dc6be9b0c733a8850b9b3b40c74.
Independent stack, not reconciled with Maya #410/#72 or RC12.

## Playable scope
The existing race, baton relay and flag-game systems now validate authored
courses against the world's selected registry. A combined world accepts its
existing Kanto map coordinates; default Hoenn worlds still reject them.
Map labels, ready pads, checkpoints and handoff targets use that same registry.
No preset Kanto course, asset import, new native script or save change is added.

Authors can use world.inspect_campaign_destinations from #435 for bounded map
metadata, then existing world.publish_race / world.publish_flag_arena tools or
the existing relay-authoring interface. Exact map bounds are not walkability,
pathfinding, accessibility, fair-course or collision proofs. Playtest any
authored route using normal native controls and personal progression. No
blocked story route becomes accessible because it appears in a course.

Players use existing /guild play list/start/share/join controls or the specific
/guild race, relay and flag commands. Invitations and readiness remain explicit.
Normal native movement reports drive ordered checkpoints, adjacent baton
handoffs, flag pickup/tag/return and completion. There are no synthesized
movement commands, warps, missing checkpoints or native battle results.
Records are recreational client-position attestations, not anti-cheat evidence.
No Pokemon XP, money, inventory, badges or personal story flags are awarded.

Current matching LINK admission is required for an active position to count in
a combined world. Stale/disconnected/unadmitted positions cannot advance play.
Existing cancellation/timeouts and private durable records remain unchanged;
server restart does not fabricate completion or resume an unfinished game.
Race and relay definitions are revalidated when loaded, not just when authored.

## Verification
40 focused tests pass, including five new combined-region tests. Actual
authenticated HELLO/LINK/CHAT/STATE authority handlers exercise two-player
race progress and private restart records, ordered relay handoff, flag capture
versus disconnect, missing admission, wrong bounds and default-world rejection.
Fixtures use mocked transport and authored test coordinates; they are not
rendered route playtests. Existing Hoenn activity and combined campaign tests
also pass. No full engine build, live two-client native movement, mounted
Kanto visual QA or disk save/reload test is claimed. No provider calls.
