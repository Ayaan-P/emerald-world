# Generated-world data experiment

This is an experimental data path for generated worlds. It is not wired to the
live server, the native game, a model, a renderer, or world creation. It cannot
create a playable map or guarantee a safe in-game landing. No existing saves or
worlds are read or changed by these functions.

## What is implemented

- `world/procedural_map.py` accepts a bounded, inert plan and creates a
  deterministic connected grid from a specified 64-bit seed. Its SHA-256
  counter algorithm, ordering, format and content hash are versioned. A model
  may also propose a grid as data: unknown fields, code, unknown symbols,
  disconnected floor, invalid exits, overlap and out-of-bounds positions are
  rejected. Model output is never run as code.
- `world/generated_map_store.py` validates and persists API-immutable,
  content-addressed blueprints in a caller-supplied SQLite connection. It
  revalidates on read, supports transaction rollback and enforces bounded size
  and entry count. It does not open a world or commit a caller's transaction.
- `world/generated_map_wire.py` frames validated maps in bounded ASCII chunks;
  a receiver assembles and verifies the entire canonical document before
  returning it. Partial, conflicting, corrupt and oversized transfers do not
  produce a map. Authentication, authorization, transfer timeouts and replay policy are
  deliberately outside this prototype.

Run locally with `python3 -m unittest discover -s test/world -p 'test_generated_map*.py'`
and `python3 -m unittest discover -s test/world -p 'test_procedural_map.py'`.
The focused checks cover 100 seeds, cross-process repeatability, malformed
proposals, save/rollback of disposable SQLite databases, packet reordering,
truncation, and two local socketpair clients receiving the same blueprint.
These are Python/data-path tests, not native clients or multiplayer acceptance.

## What is still required for an actual shared generated world

1. A server-owned generation, approval and publication flow. Authenticate and
   authorize creators and recipients, persist authoritative versioned map
   identities, handle disconnect/reconnect, rate and storage limits, and avoid
   leaking private world data. A content hash is an integrity identifier, not
   proof of authorship or permission.
2. A real native map instance and tile/sprite palette with proven semantics.
   Abstract `.` and `#` do not describe elevations, collision behaviors,
   animations, warps, scripted events, dynamic occupants, or usable art.
3. Atomic admission and safe spawn/exit/return when players join, reconnect,
   or are already present. Changes must not trap players or alter existing
   story-critical maps, private saves, parties or inventories.
4. Integrate with the existing protocol rather than assuming the experimental
   `GENMAP1` frames are recognized. The current bridge has bounded tile and
   snapshot buffers; arbitrary generated worlds require a compatible versioned
   streaming/instance design, not simply raising a limit.
5. Real multi-client native gameplay, rendering and recovery tests. Generated
   map reachability in this prototype is abstract grid connectivity, not proof
   that a Pokémon trainer can traverse the resulting engine map.

No LLM is called here. An eventual model can propose a bounded plan or grid,
but server-owned validation and authorization must remain independent of the
model's instructions.
