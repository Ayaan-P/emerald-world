# Whole-source candidate, not a release

`auto-engine-*.patch` is the mechanically merged engine-related subset of
RC8's changes against the pinned Expansion donor. The parent branch contains
RC8's server, launcher and other project files directly. The complete merge
reported 62 conflicts; conflicted paths were not silently declared resolved.

Initial explicit resolutions combine the World menu with Expansion's existing
DexNav/debug menu, adapt the generated-layout hook to Expansion's parameterized
map lookup, preserve the donor's script-special order, and add World scripts.
`src/menu.c` additionally accommodates the tenth possible start-menu entry.
These resolutions need compilation and graphical verification.

The two generated maps are inserted as group 34 to preserve the existing
World protocol, shifting later donor map-group numbers. Existing Expansion
saves at or beyond that group are **not compatible** without migration. Use
fresh disposable profiles. Previous saved data is never automatically copied.

`world-runtime.patch` reuses the earlier RC7 native loop integration; it is
being reconciled with the newer mechanically merged World code. The build
wrapper propagates the same feature flags to the donor's pointer-width
reference builds rather than disabling its relocation checks.

Battle, save, object, renderer and other conflicts remain; this candidate is
not playable or safe to release. See `conflicts.txt` for the original list.

The `src/link.c` conflict resolution reuses the prior donor virtual-cable port
and exposes the World block-size API. It is not a validated co-op or trade
integration. Cross-engine offers are now rejected by the server compatibility tag; this
has only been checked with in-memory protocol tests, not real network sessions.
LINK compatibility and session recovery still require end-to-end verification.

Initial field-input and link conflict resolutions carry the existing World
hooks into the donor's field and virtual-cable code. The save conflict uses the
Expansion platform's `frame_flush_save` instead of the old native save writer.
Save failure/retry semantics and real-network LINK isolation are still
unverified; these source merges must not be interpreted as safe gameplay.

The 17 existing World implementation modules and 20 matching headers were
three-way merged from the earlier Expansion adaptation, the RC6 World source,
and the RC8 World source. No textual conflicts were reported in those files;
this does not establish ABI compatibility or gameplay correctness. Exact input
and output hashes are recorded in `world-port-provenance.json`. The earlier
adaptation targeted the 1.17.2 foundation; this candidate targets the pinned
1.17.1 donor, so compilation and reconciliation are required.

The prior Expansion adaptations of battle setup, object events and Fly have
been carried forward with the missing RC8 trainer, remote-collision and arrival
hooks restored. This does not establish co-op, rendering, travel, DexNav or
save correctness. The earlier battle-controller adaptation omitted World packet validation and
co-op hooks; those have now been source-merged separately and require compile
and protocol verification. Treat the result as experimental, not safe online.

Expansion's own DexNav input and Repel/Lure menu are used in the candidate;
the World-only RepeatRepel implementation is excluded from compilation. The
World menu entry is connected to Expansion's DexNav through the prior source
port. Exact behavior, including multiplayer restrictions, is not yet verified.

The earlier native sprite tile-bank and OAM source changes are carried over
against the pinned donor to satisfy object-event hooks. Renderer integration,
capacity, ordering and visual correctness are not verified.

The earlier native renderer's extended OAM and OBJ tile-bank changes are
carried into the donor platform library. Its separate build receives explicit
feature flags. These changes must still be built and visually tested.

The native EWRAM mapping and linker region are expanded from 256 KiB to
512 KiB for this candidate, while retaining a size assertion. The platform
mapping and game-side bound are changed together; pointer relocation, reset,
heap behavior and saves still require verification. This does not change a
GBA ROM's memory map.

The opening replay crashed in ScriptMovement_MoveObjects. Its original task
storage holds 16 completion bits, while World configures 48 object events.
The candidate now stores native movement IDs and 64-bit completion state
separately. This is a suspected fix and requires the replay to pass.

The offline opening replay completed through save and cold restart. The only
screenshot difference was the start menu; the actual image was reviewed and
shows the added WORLD entry without obvious clipping. Only that expected hash
has been updated; other donor screenshot and state expectations stay intact.
