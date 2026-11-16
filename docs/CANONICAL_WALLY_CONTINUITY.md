# Wally continuity at his original later-story locations

## Why not convert the story Ralts into the dynamic practice seed

The exact Expansion trainer data uses Ralts level 16 with all IVs 3 at Mauville, then Gardevoir level 45 with all IVs 30 and explicit Double Team / Calm Mind / Psychic / Future Sight at the first Victory Road battle. Later rematches have their own presets. These are separate scripted roster constructions, not a stored individual Pokémon that the world authority can faithfully resume. The current dynamic INIT1 IV15 seed is not that original individual. Scripted progression must not be called agent-earned training, and a species/IV replacement must not silently overwrite original battles.

This batch therefore preserves every original roster and battle/rematch command. It implements a different concrete existing-cast capability: the same ongoing authored Wally can continue talking with the player where Wally actually remains later in the story, not only at Wanda's house.

## Reviewed native entries

- Wanda's house keeps the existing lock/faceplayer supplement.
- Victory Road entrance Wally's direct conversation now uses explicit lock/faceplayer, the same original text, and release. This is equivalent to its original MSGBOX_NPC standard script, with the optional supplement inserted after the safe prefix.
- The exit and rematch branches retain their original trainerbattle commands, ShouldTryRematchBattle check and branch order. Only their completed-conversation continuations converge at a lock/faceplayer wrapper around the original post-battle message and release. DEFAULT plus release is equivalent to the original AUTOCLOSE standard script sequence.
- The automatic approach/entrance battle trigger is not intercepted. No battle is skipped, replaced, auto-started by this feature or marked complete.

The native supplement requires the current player's existing FLAG_DEFEATED_WALLY_VICTORY_ROAD and refuses while gMain.inBattle. No flag is written or synchronized across players. Original text resumes on old-server refusal, disconnect or the existing bounded timeout. The script retains ownership of its lock.

## Same character, independent trainers

`wally_vr` resolves to the same `canon_wally` record with a reviewed VictoryRoad_1F location, not a duplicate NPC or independent persona. Authored world goals/dialogue, explicit personal choices, private encounter summaries and their opt-ins retain their existing semantics. Private summaries remain keyed by trainer/save/actor across both locations. The location-specific display receipt cannot be acknowledged from the wrong map or alias.

The minimal native CAST exchange records a connection-local location/lineage context. Existing guild-chat actor actions at the later location require that original conversation first. Another trainer or a different save does not inherit this context. Current field location is checked again; leaving the map removes access to those actions. No player's story stage is published to shared world history. This is ordinary authenticated client attestation, not an anti-cheat claim.

## Validation and limits

Tests cover actual authority house-to-Victory-Road continuity, one private actor record, wrong-map/alias refusal, independent trainers/saves, restart, native flag/in-battle gating, timeout/original continuation, unchanged trainerbattle commands/rematch branching, and exact original Ralts/Gardevoir preset anchors. A source test checks original DEFAULT/AUTOCLOSE message semantics.

Full linked script assembly, rendered conversation/battle continuation and both late Wally locations still need Maya's QA. No live model, player save, story team mutation, species evolution or earned canonical Pokémon development is claimed. The separate dynamic recurring-character practice system remains distinct until a reviewed canonical individual-identity design exists.
