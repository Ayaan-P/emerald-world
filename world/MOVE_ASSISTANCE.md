# Voluntary NPC move assistance

Independent draft on app #423 (`5bdeec1e2f8174324c6ba4ee04be1d7a49332dce`), not Maya's #410 or RC12. Existing native #79 is unchanged. No held file or uncertain operation is included.

## Playable interaction

Face an authored shared prop while beside an active generated NPC. Use `/guild object ask-help NPC ACTION` for an advertised player move action. Read the public-request disclosure and send its confirmation command. This publishes the object/action, not the player's login or party. The request is not a command the character must obey.

An enrolled author receives the real request through the existing queue. It can decline, ignore it, or choose `world.respond_move_help` with an owned on-team individual and a currently reconciled native learned move. The author may need `world.inspect_moves` first: changing character version invalidates old native inspections. No new provider is started by this feature.

The selected move is only an offer. `/guild object help-status` exposes the response and `/guild object help-accept ID` inspects the current action. The player explicitly confirms its token while still facing the object beside the NPC. The NPC must also be cardinally adjacent to the target. The existing authority move executor then stages the actual shared effect. Its normal object/character revisions, native ownership/move proof, authored action and geometry guards all remain active.

This second confirmation is essential: an NPC plan admission changes the mechanic source, and the ordinary object revision includes its source hash. We do not weaken or bypass that revision check. The final token binds the current source-dependent object revision and NPC version. Changed offers need inspection again.

The ordinary prop program can change text, graphics, positions or cooperative phases. For example, a fixture uses a genuine player contribution and a genuine NPC contribution, followed by an independently chosen NPC release that moves a second prop. This is a test of a general mechanism, not a built-in quest. Cooperative contribution identities are unchanged; assistance does not fabricate an extra human contribution.

## Boundaries and recovery

- Five-minute session-bound request, explicit public disclosure, no long-term player/NPC identity link or relationship appraisal.
- Four open requests per session/account and one unresolved request per NPC. Expired/disconnected unsubmitted offers release capacity.
- `/guild object help-stop ID` prevents new submission. Once submitted, ordinary authority admission settles honestly; the terminal status says `completed_after_withdrawal` if appropriate. It does not roll back world changes or prohibit independent NPC actions.
- Current plan and pending step must still match at final confirmation. A replaced/blocked plan releases capacity as `unconfirmed`, never a claimed success.
- Durable pending data and the existing capability runtime distinguish a submitted action from completion. Restart before dispatch/admission yields an honest unconfirmed outcome, not an automatic replay. A never-confirmed request ends without action after disconnect/restart.
- Completion points to the actual committed learned-move receipt. If the object changed again before ordinary polling, completion is conservatively unconfirmed even if historical effects exist. No player-goal success is inferred.
- No player party, inventory, story, reward, PP, capture or battle change. Shared object moves retain their existing no-PP semantics. No canonical NPC relocation, native worker change, or new native menu.
- UI is existing guild commands plus actual native shared-object rendering. No automatic player notification or guaranteed author response; use help-status. Renderer/two-client QA is still required.

## Verification

`PYTHONPATH=.:test/world python -m unittest test_move_assistance test_actor_runtime test_cooperative_moves test_player_npc_memory test_npc_conversations test_author_capability_loop test_character_reactions test_actor_objects`

57 tests: 55 passed, 2 existing sandbox/provider skips. Native MOVES1 inspection data in the new integration test is explicitly synthetic; actual authority capability scheduling, object admission, cooperative state and visible position changes are exercised. No live model, current-native full build or rendered gameplay test was performed.
