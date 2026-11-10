# History-driven native habitat populations

An app-only capability for revising the actual land encounter table of an
existing shared generated cave. This is not a simulated ecosystem or a claim
that Pokemon migrated, bred, were caught, or defeated anyone.

## Player-visible effect

The configured author can inspect the active cave and compose
`world.revise_habitat` after that real inspection. It selects twelve native
encounter slots (enabled Expansion species and levels) and an encounter rate.
The authority creates and archives the changed CAVE10/11 bytes, retains the
same logical place ID and exact walkable geometry, and records a causal
before/after population event in the same transaction as the tool receipt.

On subsequent entry, a compatible native client receives those actual wildlife
bytes through existing CAVE WILD transport. The ordinary native encounter and
battle machinery consumes them. Existing native weighting, terrain/encounter
checks, Repel behavior and battle rules are not reimplemented here. A changed
configuration is not proof that a particular player encountered anything.

This also gives an existing plain shared cave its first explicit Expansion
population without inventing a new place or replacing its geometry. A previously
plain cave needs one of the supported native cave profiles; an existing profile
must remain unchanged. The author can react to real history using normal plans
and event subscriptions. There are no fixed species lists, named-character arcs,
automatic seasonal changes or fabricated population counts.

## Interface and boundaries

- `world.inspect_habitat()` returns public authority configuration, stable place,
  exact revision, side, native profile, cohort, rate and twelve slots if present.
  This is not a character's eyesight or a player's private Pokedex.
- `world.revise_habitat(observation,profile,rate,slots)` consumes that actor's
  successful inspection receipt. `slots` is JSON containing exactly twelve
  `[species_name,level]` pairs; enabled-species validation comes from the existing
  compiler-exported Expansion catalogue. Rates and levels are 1..100.
- Supported active shared formats: plain/profile/legacy wildlife/Expansion
  wildlife caves, 31 or 63 tiles per side. Output is format 10 or 11.
- Every shared-slot visitor must leave before a real revision. Existing reset,
  stale ACK and legacy-client refusal semantics remain authoritative. Other
  independently selected regions are unchanged.
- Opened immutable regions are explicitly refused. This does not revise linked
  cave destinations, enable outdoor REGION1, modify XL/outdoor tables or change
  original Hoenn encounters. The earlier uncertain outdoor operation is excluded.
- Current profile and geometry are preserved. Existing source/character rebinding
  validation is retained; no actor, carried object, battle or save is silently
  moved. Known revisions cannot be reassigned to a different logical place.
- No-op tables return unchanged; invalid/stale/occupied changes and final receipt
  failures produce no new habitat revision. Existing archived revisions persist.

## Pairing and verification

Based on app #338 with unchanged published native #40 pin
8e409094ccd226a66c9cf8bfef2f545f2be52c28. No native source upload and no unpublished
doubles code. Tests cover both map sizes, two independent canonical author
records, retained place/geometry, restart/no replay, actual authenticated CAVE
transport, legacy refusal, invalid species, stale/occupied/immutable refusal and
receipt rollback. A compiled existing native WorldCaveWire decoder consumes the
revised table in the paired component test.

No live provider, rendered encounter, catch or player save was used. Maya owns
full linked/multiplayer integration, gameplay QA and release.
