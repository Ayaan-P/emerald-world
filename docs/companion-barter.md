# Independent reciprocal companion exchanges

This app-only slice adds `world.propose_exchange` and `world.resolve_exchange`
to the existing provider-neutral character capability runtime. It is based on
published app #335 and its unchanged native #40 pin. It does not contain or
require the unpublished Doubles implementation or modify its blocked files.

Two adjacent, stationary world-owned trainers can negotiate a reciprocal trade
of two **existing benched individual Pokemon**. The initiator names both current
individuals and the local aliases each recipient will use. The proposal freezes
both actual roster/training snapshots. A real public offer event can wake the
recipient's already configured independent author. It never chooses acceptance
on the recipient's behalf or starts a provider automatically.

Acceptance rechecks adjacency, ownership, bench status and both frozen states.
Both custody transfers, outcome event and capability receipt commit in one
transaction. A second-leg failure or receipt failure leaves both originals with
their previous owners. Decline and withdrawal change neither roster. One open
proposal per unordered pair bounds active inbox growth; completed history is not
a lifetime trade limit. Return trades reuse historical aliases instead of
creating a new native identity.

Species, personality, original trainer identity and any trusted full native
training bytes survive unchanged. Provenance records remain, but cannot be used
to resurrect a Pokemon after custody has moved. Active teams are not silently
rewritten: either NPC may independently choose its new bench member through the
existing `world.prepare_challenge` capability. Players then encounter that real
individual in the existing optional native battle. This is a material roster
change, not a claim that a trade animation, friendship, evolution or training
occurred. No player Pokemon, bag, money or save is involved.

## Verification

Tests use actual authority plans, persisted custody, independent recipient
reaction queue, restart, reciprocal return, second-leg/receipt rollback, frozen
bench status, exact opaque full-state preservation and admitted challenge lineup.
Existing one-way gift tests still pass through the shared transfer primitive,
including authenticated native challenge transport. No live model, native trade
animation or rendered subsequent battle was run. Maya owns integration and QA.
