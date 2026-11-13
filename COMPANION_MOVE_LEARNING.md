# Owned companion move learning

This candidate adds two general agent capabilities: `world.inspect_moves(individual)`
and `world.learn_move(individual, move, slot)`. An autonomous generated trainer can
inspect its actual individual Pokémon's native Move Reminder choices, choose one
and a replacement slot, and later challenge a player using that retained full
Pokémon state. No fixed character arc, extra player chore or invented victory.

## Connected path

The individual must already be on that actor's team, owned in the companion
registry and have reconciled full native state. The normal actor plan runtime
queues a durable request. The existing session-managed practice worker processes
it under the same host-configured recurring per-actor budget. Inspection and
learning each consume one host turn. This worker remains off until the host
attests that the exact executable passed isolated-entry QA.

Native #50 (`75719749b0009a585a5803255af3cdf597e0f058`) implements MOVES1/LEARN1 in
the one-request scratch process. It uses the existing level-up Move Reminder
selector, respecting that binary's all-level/pre-evolution settings. These moves
are not necessarily earned from battle. It uses ordinary RemoveMonPPBonus and
SetMonMoveSlot operations. TM/bag, egg and tutor categories are not exposed.

The host freezes the full source and executable digest, claims before execution,
checks legal choices again, verifies the changed slot and unchanged identity,
level and experience, then durably stores the receipt before authority application.
The authority rejects changed plans, versions, ownership or prior state. The
existing CHARPK2 optional battle path sends the new opaque full individual state.
Player parties, bags, save files, canonical story teams and normal scripts are not
modified. Move names are descriptive labels exported from the exact native move
constants; native numeric eligibility remains authoritative.

A lost authority acknowledgement is retried from the stored result without
re-running learning. A crashed native execution is not automatically replayed.
Invalid native choices report a failed result to the agent, allowing a new plan;
withdrawn/stale plans cannot apply their result. A local result refused by changed
world state remains quarantined for host recovery, not silently rebased. Existing
full states from another executable are refused; there is no automatic ABI migration.

## Integration and verification

This is cumulative on app #358 and native #49, not the released RC12 pair. Maya
must preserve release fixes when integrating. The app gitlink, builder and
candidate manifest pin native #50. Habitat metadata inputs were unchanged by its
five-file native diff, so its exact provenance is carried to the new pin.

Tests exercise actual authority requests, plan polling, worker lifecycle,
reconciliation, optional-battle descriptor and restart using explicitly fake
engine storage. Separate C tests compile the production CLI with mocked Pokemon
APIs and the actual level-up selector against varied configuration/learnset
fixtures. These are component checks, not a linked game or live model playtest.
Full linked native storage/PP behavior, isolation and a rendered later NPC battle
remain Maya's QA gates before enabling the runner. No live provider call or
player save access was used.
