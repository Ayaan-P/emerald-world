# RC7 port contract: preserve the working co-op subsystem

This is a contract map, not a completion claim. Original working source is
`src/` + `src/platform/` in the app repository. Expansion target source is
`engines/expansion-native/src/` + `src/world/`. The task is to adapt the existing
native co-op system to Expansion, not independently reinvent its features.

## 1. Identities and execution

The transport has two authenticated participants (0/1); a co-op battle has four
roles. The engine master is participant0; its NPC controllers supply roles1/3.
Ally0 is owned by participant0; ally2 is owned by participant1. Encounter owner,
engine master and private action owner are different concepts.

Original: `src/battle_controllers.c` NativeBattleMaster/NativeBattleOwner/
NativeBattleSourceValid. Original outbound code suppresses non-owner
B_COMM_TO_ENGINE responses while mirrors still acknowledge visible commands.
These rules must survive the port; merely copying buffers is not equivalent.

## 2. Startup and transport participant counts

Original `src/battle_main.c` CB2_InitBattle checks WorldCoop before ordinary
four-human Multi Battle selection. WorldCoop already exchanges and validates
both selected allied sets and the encounter owner's NPCs, then stages them.
Stock Multi Battle cannot replace those parties, elect a PvP master or await
four human consoles. Expansion startup now has a two-owner header/berry branch.

Original controller SENDTASK_STATE_COUNT_PLAYERS explicitly includes WorldCoop
in the two-player case. The missing equivalent was restored in engine fb9e7bde1a.
Four battlers do not imply four transport peers. Neither correction alone proves
that every later request/reply/ACK contract was preserved.

## 3. Party layout and data representation

Original BuildPrivateParty reads selected allies in two three-slot ranges of
one staged player array. Expansion has separate gParties[trainer] arrays.
Target WorldCoop StageMon maps those wire-stage ranges to player/partner arrays.
gPlayerParty remains an alias for the player trainer's array, not an additional
independent save buffer. Private merge must use StageMon and stable owned slots.

Expansion BtlController_HandleGetMonData/HandleSetMonData use
GetBattlerParty(battler), gBattlerPartyIndexes and a mask. Snapshot sizes come
from current sizeof(BattlePokemon), Pokemon and MovePPInfo. Original numeric
widths, status masks, enum/item/species IDs and save offsets cannot be copied.

## 4. Ordered controller request/reply/completion

Original native boundary preserves authenticated packet source beside each
FIFO record, validates lengths/commands, records the pending request per battler
at dispatch, accepts one matching owner reply and then retires the real DONE
flags through normal dispatch. Source identity, pending reply use and controller
idle state are separate invariants. Full-six roster and medicine replies must
be demultiplexed by the request that authorized them, not only by body size.

Original PrepareBufferDataTransferLink filters mirror engine replies and
serializes the one-byte DONE identity into a padded cable record without reading
three bytes beyond that byte. Target stock sender does not preserve those native
extensions automatically. Preserve FIFO ordering and normal ACK handling; do
not clear flags to make a stalled game appear ready.

Original native receiver also checks ring bounds/wrap and complete command
lengths before enqueue/dispatch. Current target receiver is not the complete
ported boundary; the dispatcher worker owns that coherent missing delta.

## 5. Intro ordering: original semantics versus Expansion

Original BattleIntroPrintWildMonAttacked waits gBattleControllerExecFlags==0
before emitting the next text command; the surrounding original intro phases
similarly drain previous controller work before advancing.

Expansion combines intro into DoBattleIntro states. In INTRO_TEXT and several
other transitions it checks IsBattlerMarkedForControllerExec(player-left).
For LINK this helper checks only that battler's outbound synchronization bit,
NOT all active controller flags. A completed enqueue does not mean the prior
visible command and its DONE acknowledgements have drained.

Actual build21 data, not a successful battle:
- Host: intro8, exec100000ff, send3:1000/1000, recv1548/1768.
- Guest: intro0, exec000000ff, send3:768/768, recv1548/1768.
- Both: all bufferA command IDs52 (TERMINATOR_NOP), bufferB IDs28 (DATATRANSFER).

Those observations are consistent with a later same-battler controller command
at FIFO head blocking preceding completion ACKs queued behind it. Exact causality
still needs verification. The adaptation must retain the original co-op intro
barrier while allowing tasks/controllers to run and drain normally; no forced
idle/queue bypass, arbitrary timeout success or flag clearing is acceptable.

## 6. Private completion and return

Original and target keep the same intended lifecycle:
validated staged battle -> local party merge/identity validation -> bilateral
READY -> matching COMMIT and own echo drain -> private reward/evolution flow ->
restored owned party and field callback. Abort before commit restores the owned
snapshot, refunds pending medicine as appropriate, and does not silently save.

Target BuildPrivateParty uses StageMon and identity checks; PreparePrivateRewards
restores only the local party and active slot, resets reward presentation, then
closes link and moves to private rewards. gBattleMons on the guest is a UI mirror,
not the master simulation or an authority for inventing private rewards.
Held-item restoration, capture delivery and owner-only spending have additional
pending changes and are not accepted merely because these functions exist.

## Implementation boundary

Adapt the original subsystem contracts deliberately to Expansion's explicit
battler arguments, split trainer parties and current canonical data layouts.
Keep ordinary non-co-op behavior outside native/co-op guards unchanged.
Read complete producers, dispatchers and cleanup paths before accepting an
export. Commit actual source batches and keep the current source-only Git
handoff synchronized. No newer Dot branch or trading work is part of this task.
