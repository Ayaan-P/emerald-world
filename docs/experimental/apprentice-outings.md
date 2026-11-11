# Apprentice outings (default-off draft)

## What the player can actually choose
Finish the original Battle Tower apprentice mentoring conversation first. In a free Tower lobby visit, enter `/apprentice start` in the existing game chat overlay. `/apprentice` explains the limits; `/apprentice status` and `/apprentice end` inspect or end the session.

Your own latest completed native apprentice record supplies three species, their advised moves and their lead order. The existing native apprentice factory generates their battle party at its normal Frontier level. On ordinary Hoenn route/ocean/cave wild encounters the apprentice joins as a native AI partner. The native partner introduction/name and switching use that apprentice's Frontier identity, not Steven's identity. There is no walking sprite in this first slice. This is a local battle companion, not another human in co-op.

The companion retains HP and PP across encounters in this RAM session. The player's full party is never reduced, reordered, copied into the partner bank or restored to a prebattle snapshot. Player damage, PP use, EXP and native capture rules remain real. Normal defeat/whiteout still applies. An exhausted companion ends the outing. Start a new outing at the Tower to generate a rested team; this does not train, heal or rewrite the saved apprentice template. No added fee, timed tax or fabricated scarcity.

Human co-op admission, a pending Steven invitation, existing followers, explicitly solo fallback and double/special/scripted battles retain priority. Generated maps, other regions, Safari, Pike, Pyramid and Trainer Hill are excluded. The feature does not grant badges, rewards or story credit.

## Ownership and lifetime
All new state is RAM-only. Native NPC followers remain disabled, SaveBlock3 does not grow, and the saved mentoring record is read-only. Its checksum, teacher ID and exact record bytes are checked before each admission. A changed record, changed region or disconnected world connection ends future participation. Disconnect during a local battle does not confiscate its results or abort it: the battle finishes normally and the prior partner bank/count/ID is restored. New-game lifecycle discards session state. Restarting the process loses the outing, not saved mentorship.

Advised held items stay at the Tower. Outing Pokemon start without items, and native get/lose-item checks reject cross-battler transfers involving the companion, including Trick/Bestow/Symbiosis/stealing paths through that shared predicate. This prevents generated loan equipment or the player's private equipment from crossing into the companion bank. Ordinary player-versus-wild item behavior is unchanged. The restriction is deliberately stronger than ordinary partner item exchange. The companion party is generated from a template, not a persistent world-owned individual or a published copy of the player's Pokemon.

## Implementation
- `world_apprentice.c`: bounded RAM session, validated native record, actual native factory, independent partner bank, status/commands, entry and completion.
- `battle_setup.c`: after existing human/Steven admission, ordinary wild entry and original return/whiteout callback.
- `battle_ai_main.c` and `difficulty.c`: apprentice identity never indexes the normal trainer/partner arrays for AI/difficulty. Existing Frontier name/front-sprite rendering is reused.
- `battle_util.c`: existing item-transfer predicate enforces the companion boundary.
- Existing chat and core lifecycle callbacks provide entry and cancellation. No bridge change or new transport protocol.

## Verification and remaining QA
Three automated tests pass, including compiled C with UBSan in both flag states. The C harness invokes the actual module, actual native `DoStandardWildBattle` and `CB2_EndWildBattle`, and actual AI/difficulty functions. It exercises start, invalid/changed record, human priority, solo fallback, Steven priority, special/double/generated-map exclusion, retained companion HP/PP, untouched player party during admission, retained player damage, restoration of the prior partner bank/count/identity, loss/whiteout, exhaustion, disconnect during battle and explicit end. Other tests check lifecycle/chat/item hooks and absence of player-party rollback/save writes.

Engine services and Pokemon generation are stubbed in this harness; it is not the full battle engine or a rendered playtest. Header-based syntax checks pass for the new module and difficulty source on/off with recovered native headers. Broader syntax checks hit missing/stale recovered headers (`kanto_rematch.h`, `world_character.h`, tutorial declaration), so those are not claimed as full compilation. No exact full native link, actual apprentice sprite/animation, rendered chat, switch/hazard interaction, item-move battle execution, capture, loaded-save or linked-client QA has been performed. No real saves used.

`EW_APPRENTICE_OUTINGS=0` by default. The app option `--experimental-apprentice-outings` requires `--development`. Keep disabled pending Maya's integration and native QA.

## Walking follow-up boundary
Do not enable `FNPC_ENABLE_NPC_FOLLOWERS`: its saved struct changes the stock save layout. A walking extension needs an independent transient object lifecycle with collision/warp/slot failure handling and no saved script pointer. The battle session API can be reused, but this draft neither implements nor claims that walking lifecycle. No persistent world-history report or agent action is installed; the enduring consequence reused here is actual native saved mentorship.
