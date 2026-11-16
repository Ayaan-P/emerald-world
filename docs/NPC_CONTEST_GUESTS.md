# Optional recurring-NPC contest guests (draft)

A world-owned recurring NPC already placed in `LilycoveCity_ContestLobby` can use `world.enter_contest(category, individual)` to offer one of its actual on-team individual Pokémon for a Normal-rank contest. Categories are cool, beauty, cute, smart and tough. Empty individual withdraws that actor's entry. One entry per category; another actor cannot replace it. Native trainer names are limited to seven ASCII letters/digits/spaces. This is a general action, not a prescribed character arc or default event.

Players enter through the ordinary Lilycove receptionist, choose category/rank and their own eligible Pokémon. If a matching guest exists, the receptionist asks whether to invite that guest. No slash command is required to play. `/guild contests` optionally lists entries. Accepting replaces one of the three ordinary NPC opponents; two original opponents and the player's chosen Pokémon remain. Declining or losing the connection leaves the normal contest intact. Link contests and higher ranks are unchanged.

## Pokémon and game boundaries

The authority resolves current owned identity and on-team membership each snapshot. It does not create a species, transfer ownership or move the NPC to the lobby. A trainer must already have an actual lobby object. If the actor leaves, retires or no longer owns the individual, the offer disappears. This does not implement autonomous Hoenn travel.

For untrained companions, native construction uses the existing persistent opponent semantics: fixed personality/OT ID, IV15, native initial moves and untrained condition. For saved full-state companions, existing CHARPK2 validation checks the 100-byte native Pokémon and matching identity before a local copy is read. Moves, nickname, shininess, condition, sheen and native scarf effects come from that copy. No invented contest training/condition is supplied. The selected Normal-rank AI remains native. Imported opaque snapshots retain the existing exact-engine/ABI limitations; no new save migration is provided.

The normal contest runs after the invitation. Player ribbons/prizes and original scenes are untouched. This feature does **not** report or persist a contest win for the NPC, award an NPC ribbon, mutate its stored Pokémon, or claim it traveled/participated merely because entry was offered. It does not modify player party data to construct the guest.

## Transport and recovery

CONTEST1 is an optional final HELLO suffix, peeled before OUTBREAK1. Older servers retry without it; older clients receive no guest rows. A CONTEST_GUEST snapshot row freezes actor/revision/category and actual identity/state. Rows are only delivered while the player reports the real lobby. The native offer is frozen before consent and rechecked against current live snapshot on acceptance. Map changes, disconnect, stale snapshot, changed identity or duplicate apply refuse the replacement. Snapshot admission is atomic; no saved guest state or script execution crosses the wire.

## Validation / integration

Actual authority plan execution, ownership/location checks, restart/withdrawal, legacy clients and real native parser/offer/apply C functions have component tests. Native fixtures stub engine Pokémon access/construction and scoring; they are not a linked rendered contest test. Maya still needs actual receptionist/party selection/appeals/results, language/text layout, save/reload, link-contest isolation and two-client QA. No live model calls were used.

Based on app #349 and native #45, not released RC12. Released app f484577b606348d07337387f14f75ab8cf4970b6 and engine f7a813317d1b9fec803b48b682f5d74245c79037 are untouched. Preserve Maya's release fixes during integration; no merge or release is performed.
