# World memory: build on what actually happened

## Decision and first slice

A persistent world needs a memory of its places and changes, not a second save
format and not a story that a model invents after polling. Keep `world.sqlite3`
as the authority, keep native trainer saves private, and give the next builder a
bounded, readable view of confirmed history alongside the current world.

This candidate starts from RC10 app checkpoint
`d03b4f668d5d8e1ac388341e9d8d0cad407f69ad`. It does not change the Expansion pin,
merge the wildlife experiments, or change a running world.

The first usable loop is:

1. A host publishes an area, edits its shared terrain, or commits a mechanic.
2. The authority writes the actual change and a historical event in one SQLite
   transaction. A failed history write rolls back that change.
3. A later GM request receives current shared state and recent historical
   evidence through `inspect`, then retrieves request-matched old evidence and
   first recorded place changes through `world_recall` at that same sequence boundary, including
   after restart.
4. The author preserves those facts while proposing another tested mechanic.
   The existing staging, tests and deployment authority still decide whether
   that proposal takes effect. Text in history cannot grant new authority.

No model is called merely to maintain this memory. Two changes between GM polls
remain two events. A state-only mechanic tick or routine NPC walking does not
become a new world milestone.

## What is recorded

New `world_memory` entries use the existing monotonically increasing `events.seq`.
The entry includes a schema version, host recording time and
`evidence: authority_commit`. Sequence, not wall-clock time, determines order.

- Durable area activation and explicit name changes: logical place ID, content hash, previous active hash
  and whether the host explicitly continued the same place.
- Shared terrain and geometry: logical place ID, template hash, terrain revision
  and changed coordinates with named before/after terrain. `original` means the
  template's terrain, not a guessed grass tile.
- Mechanic deployment and visible content changes: old/new module hashes, current
  interaction cursor, before/after public tiles and NPCs, and stable native map
  references. Deployment does not prove that a player completed a quest.

Module state, trainer saves, credentials, chat, bags and private party data are
not copied into these new history records. The old interaction log is unchanged.
The existing GM inspection still has its own module-state contract.

Existing events have no recording timestamps. Initialization records a coverage
boundary and gives existing archived areas IDs, without fabricating old events or
dates. A missing historical event means unknown, not that nothing happened.

## Place identity and revisions

`world_id` is a durable UUID inside the same database. A normal restore preserves
it. An independently forked world will eventually need an explicit fork operation;
copying a database currently copies its identity too.

Generated places get UUIDs separate from content hashes. Revisiting an archived
revision keeps its place ID. Editing a template normally creates a new place.
When the host deliberately revises the same place, it supplies the exact active
hash as `previous_revision`. The authority rejects a stale active hash and refuses
to merge a revision already assigned to another logical place. The new revision
and its lineage are committed together. Names never determine identity.

Native map references use `native:<catalog name>` within `world_id`, rather than
numeric map slots. Distinct catalog names across regions stay distinct; changing
numeric build allocations does not rename a place. Renaming catalog symbols will
need an explicit alias migration. This candidate does not claim a completed
multi-region migration or a universal cross-engine map namespace.

Logical continuity is not native save migration. Existing generated-area story
progress still uses the engine's content-derived identity and finite save slots.
Continuing a logical place does not carry old story flags, encounter outcomes or
terrain overlays onto another template. Each revision retains its own overlay.

## Read the world

The host-only admin command is `world_history`. Ordinary player traffic cannot
use it. The CLI uses the existing private admin socket:

```sh
python3 -m world.world_memory context --admin-socket /path/to/world/admin.sock
python3 -m world.world_memory history --admin-socket /path/to/world/admin.sock --limit 32
python3 -m world.world_memory history --admin-socket /path/to/world/admin.sock --place-id 'area:UUID'
```

`context` returns current public mechanic overlays and world memory, without
trainer identity rows, save paths or arbitrary module state. The GM automatically
gets recent memory through inspection and bounded older evidence through a
host-only recall request; no new model tool permissions are granted.

History pages carry `cursor`, `through` and `has_more`. Keep the first page's
`through` value while following `cursor`, so a concurrent newer commit does not
change the export's boundary. A cursor beyond committed history is rejected.
Pages contain at most 64 events and a bounded payload compatible with the existing
64 KiB admin transport. A filtered empty page still advances to its boundary.

The GM's recent context is a bounded preview, not an exhaustive history. Large
entries retain their sequence and advertise full details in history. Active
terrain previews explicitly report truncation and supply the existing full
terrain-inspection request. Older history is available through the host command;
the controller also performs the targeted full-history lookup described below.

Explicitly continue an area using the publication API or CLI:

```sh
python3 -m world.publish_cave --admin-socket /path/to/world/admin.sock \
  --previous-revision EXACT_ACTIVE_TEMPLATE_SHA256 revised-area.ewmap
```

All existing template, occupancy, persistence and admission checks still apply.
Without `--previous-revision`, the existing publication behavior remains in place.

## Read a private trainer view

```sh
python3 -m world.world_memory trainer-view --endpoint /private/trainer/player.sock \
  --output /private/trainer/readable-view.json
```

This calls only the existing native `observe` operation. It projects the fields
actually returned: frame, map/position, readiness-related flags, own numeric party
and generated event state when present. Missing fields stay missing. Unknown
fields, other players, paths and credentials are excluded. The optional output is
a new mode-0600 JSON file and refuses to overwrite any existing file.

This is a readable **live view**, not a decoded disk-save backup. It may contain
unsaved progress and cannot restore anything. Inventory, boxes, badges and all
story flags are not yet available in this projection. Native saves and the
existing backup mechanism remain authoritative. No private trainer view is
inserted into shared history or sent to the world GM.

## Research conclusions and next player-facing work

The existing server already transactionally stores mechanic source/state/overlays
and has an ordered event log. The generated-area archive already retains templates
and per-template terrain. Native observations expose owner-specific game facts.
The GM already uses inspection and verified previous source. Extending these paths
is smaller and safer than replacing them with a generic memory framework.

The next useful slice is a place journal in the launcher: select a place, see its
confirmed changes, and ask the builder to continue from that specific history.
The controller now has targeted retrieval with explicit evidence references;
the launcher should make that selection and the proposed change visible. Avoid automatic
summaries that silently become authoritative lore.

A fuller readable saved-trainer document needs an explicit engine observation or
save-decoding contract for inventory, boxes and story flags, plus freshness relative
to the last successful native save. Add it behind the same private owner boundary.
Do not infer a catch or quest outcome from movement, party hashes or disconnects.

Years-long operation also needs measured retention/backup policy and restore drills
for the existing database and native saves. No pruning or archival policy is added
here, and the event log is not claimed to replay or rebuild the entire world.
State-only tick history in the pre-existing log still has its original behavior.
This is a coherent first slice, not a claim that years of traffic, native migration,
all regions or offline player outcomes have been verified.


## Recall across older history

```sh
python3 -m world.world_memory recall --admin-socket /path/to/world/admin.sock \
  --request 'Build a Cedar bridge memorial.'
```

The GM uses the same selection automatically before authoring. Up to six literal
words from the owner's request are matched against changed public content across
all recorded history. Up to four exact places contribute their first recorded and two
latest committed changes. Explicit place IDs in the request take priority, then
the active area, observed player locations and current overlay places. Original
events and their sequence numbers are returned, not model-generated lore.

A small rebuildable SQLite projection indexes event-to-place membership and
searchable changed text. An NPC that remains unchanged in 35 later full-overlay
snapshots does not drown out its two actual historical changes. Newly recorded
changes retain their native place names in the event, so rebuilding this index
cannot reinterpret them using a later build's numeric map allocation. Older
records from the first slice retain their original, potentially broader place
references rather than inventing more precise ones. Index reconstruction adds no
historical events or timestamps. Failed index writes roll back the original
world mutation as well as the history record.

Results disclose selection reasons, a fixed `through` boundary, omitted sequences
and whether there were more literal matches. The payload stays below the existing
admin transport limit. The controller refuses to author if recall fails or returns
a different world/boundary. A legitimate empty result is allowed and remains
unknown history. The immutable GM context and report retain the selected evidence
references for review.

This is literal lookup, not semantic understanding: synonyms, unnamed landmarks
and private story outcomes cannot be inferred. Word matching scans the compact
search projection; place lookup uses its indexed membership. Years-long volumes
have not been benchmarked. Bounded selection is not an exhaustive world history,
and older evidence never overrides the current shared state.

### Concrete proposal experiment

Run the isolated authority/controller regression:

```sh
PYTHONPATH=test/world:. python3 -m unittest \
  test_world_memory.WorldMemoryTests.test_controller_builds_proposal_from_buried_evidence_after_restart -v
```

The experiment commits a keeper saying `Cedar bridge repaired.`, then commits
`Cedar bridge closed.`. It commits 35 unrelated city-guide changes that retain the
keeper in their full snapshots, closes the authority, and opens it again. Neither
bridge change is in the latest global history tail.

A new request to build a Cedar bridge memorial reaches the real GM controller.
Its recall step retrieves both old bridge changes and records their sequence
references. An injected deterministic author checks that evidence and produces a
reviewable mechanic adding an adjacent memorial NPC while retaining the current
closed-bridge keeper. The proposal is written through the ordinary immutable
candidate path. The test deliberately rejects the deployment step: it does not
pretend to run a model, pass sandbox tests or prove native rendering. The world
therefore remains unchanged by the experiment's proposal.

This verifies the missing connection from actual committed history, through a
restart and relevant recall, to a subsequent proposal. Real model quality and a
playable sandbox/native acceptance run remain separate checks.
