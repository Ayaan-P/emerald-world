# Learned moves as shared world abilities (experimental proof)

A move can be an input to an agent-authored object or linked mechanism, rather than an HM shortcut. The agent chooses the supported effect through existing prop programs. No named story, fixed puzzle or hard-coded fire/water/electric action table is required.

## Player journey

Build with `--development --experimental-field-moves` (default off). On an already supported generated map, stand facing an authored shared prop:

1. `/guild object moves` lists its current move actions and a short-lived object/revision token. This explains that the selected move/action becomes public shared-world history.
2. `/fieldmove list 1` privately shows party member 1's actual learned moves.
3. `/fieldmove 1 2 TOKEN ACTION yes` uses that member's second learned move for the selected action. The local client checks a conscious non-egg, a nonempty learned slot and a safe field context. It submits only the selected move ID/action/token, not the party or individual Pokémon identity.
4. The server checks current facing, generated-map revision, advertised action, token and existing mechanic admission. Success is reported only after the actual shared state is admitted.

Others see the ordinary synchronized prop change. The persistent `object_move_committed` record lets recurring characters inspect/react through existing public history tools. Players can decline by doing nothing. There is no automatic move use or PP expenditure.

## Agent authoring and action

Existing `world.program_object` states accept `moves:{action:[move IDs]}` in addition to `choices:[player actions]`. The former defines an any-of learned-move requirement; the latter explicitly allows players to invoke that action. Move-gated actions cannot be the ordinary A-button default. Exact IDs are native move IDs. The later MOVE_RESPONSES.md extension also accepts conservative static native type/category selectors; no inferred abilities.

Existing `world.program_network` states also accept `moves:{object ID:{action:[move IDs]}}` and `choices:{object ID:[actions]}`. Thus a move can trigger changes to linked real objects, including their existing bounded one-tile movement. Existing connected-geometry, occupancy, state-machine and publication validators still apply. Regular object use/choice cannot bypass the learned-move gate.

`world.use_move` lets a generated NPC select its owned on-team individual, an observed object/action/revision and a move. It requires a matching current, already-reconciled native move inspection from `world.inspect_moves`. Authored species/moves or stale receipts are insufficient. This does not enable or bypass the separately gated host worker. No new native worker change is included.

## Provenance and supported scope

The local player client checks the actual party, but the server cannot independently attest a modified client. History therefore says `client_reported_learned_move`, not verified ownership or battle results. NPC records say `matching_native_move_inspection`. Only an admitted shared effect is authoritative. No XP, friendship, caught Pokémon, PP cost, battle victory or automatic NPC decision is inferred.

Supported effects are those of existing generated props and networks: bounded state/text/appearance changes and collision-validated linked prop movement. This is not arbitrary terrain destruction, unrestricted Hoenn interactions, overworld combat, cross-map travel, move animations or a polished party-action menu. HM convenience remains separate and unchanged. Actual visual presentation and native runtime/save coexistence still need linked QA.

The native implementation uses the existing published local chat API; it does not modify `world_bridge.c` or introduce an alternate replacement for any denied upload. No party data is rewritten. Frozen #384/#56, RC12 and denied/uncertain operations remain untouched. This separate branch follows #408/native #70, not RC12.

## Verification

Authority tests execute real mechanic staging for two different moves, wrong-move and ordinary-choice bypass rejection, facing/revision/replay failures, failure without completion, restart, public history retrieval and a receipt-backed NPC response. A linked network test changes another real object's position. Native tests compile the actual command with fixture engine data at flag 0/1 and verify learned-slot/egg/HP/context checks, explicit consent, minimal outgoing data and no party writes. No live model or native playthrough was used; fixtures are not full engine QA.
