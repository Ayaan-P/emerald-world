# Combined-region campaigns and guild journeys

Independent parent app #434 (997f51f09a4e3501b15e98a29d35eca80b1afc08),
native #84 (659eb2ae1fd66dc6be9b0c733a8850b9b3b40c74), unchanged.
Not a reconciliation of Maya #410/#72 or RC12. No donor imports or native edits.

## Player flow
Use the matching experimental combined build and authority from #433/#434.
WORLD's existing campaign board can start or host an authored branching run.
Each participant travels using normal controls and their own available routes.
At an authored Kanto destination, Check in requires fresh ready presence and
current matching registry admission. Shared groups wait for each save-bound
participant, then use existing advice/route-choice controls. Leaving, switching
saves and restarting retain existing run semantics. Nothing unlocks a native
story gate, grants a badge or moves another participant.

Existing guilds can now use real Kanto map names for expeditions and meetups:
`/guild expedition start PalletTown_Frlg 2`
(or `here` while in the intended map). Existing membership and leader checks
apply. Guild XP is the existing authority guild statistic, not Pokemon XP or
native rewards. Public history publication remains the existing guild opt-in.

## Agent composition
`world.inspect_campaign_destinations` takes `region` (hoenn/kanto) and optional
`offset`; it returns up to 16 source-derived map records and next offset.
It supplies the exact registry digest needed by combined visit nodes:
`{"visit":{"label":"Chosen meeting","point":[38,0,6,8],"registry":"DIGEST_FROM_DISCOVERY"},"next":["another_stage"]}`

Publish with the existing `world.publish_battle_campaign`. Existing optional
battle/preparation, route choices, split roles and generated revision-bound
visits remain composable. No fixed campaign or character arc is installed.

Registry-bound nodes reject default Hoenn authorities, wrong digests and
out-of-bounds coordinates. Validation is repeated on check-in, including
persisted runs; a stale board cannot bypass admission. Receipts retain the
registry and explicitly say voluntary fresh client presence, not verified
travel or canonical story completion. Catalog bounds do NOT prove walkability,
reachability, unlocked gates or script safety. Authors must choose accessible
locations; players retain normal progression requirements.

## Important regression found
#433/#434 accepted a Kanto STATE before the downstream guild observer used the
Hoenn validator and closed the connection with MALFORMED. Their tests checked
stored coordinates but missed closure. This follow-on passes the selected
catalog/validator to both guild components. New tests require Kanto connections
to remain open after STATE and exercise actual expedition completion once.

## Verification limits
Component tests execute real authority handlers with mocked sockets, campaign
board rows, durable SQLite run state, player/save isolation, admission rejection,
and guild rewards. Existing native board and regional warp are reused.
No full native build, rendered board, linked two-client trip or disk save/reload
QA is claimed. No full Kanto campaign, new assets, auto travel, provider calls,
or held native operation is included.

Focused suite: 46 tests, 45 pass and one pre-existing error in
GuildWorldMemoryTests.test_real_completion_reaches_next_proposal_after_restart
(KeyError: history_evidence). The same exact test fails on unchanged parent
#434; it is not suppressed or counted as a pass. Six new regional tests pass.
