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
- Opted-in guild expedition/meetup completion: the existing authority goal result,
  canonical place and actual guild XP award, with its client-report trust boundary.
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

The launcher now provides a read-only place journal for local owners. The next
step is letting a player select specific journal evidence while requesting a
world-building proposal, with a visible review before any change. Avoid automatic
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


## Player-facing local place journal

Open **Local worlds → World journal** beside a world. Running and detached hosts
are readable without switching the current game. A stopped host is opened only
when the user chooses **Open host**, using the existing local-world flow without
launching a game. Hosted remote journals are not exposed by this candidate.

Select a stable place to see its committed changes, or read the whole world's
journal. Entries describe structural facts: an area was activated or renamed,
terrain cells changed, an NPC appeared/disappeared, or dialogue changed. Quoted
NPC text remains text. A claim such as “bridge repaired” is displayed as a dialogue
change, not proof that a player actually repaired a bridge or completed a quest.

The journal shows current shared mechanic NPCs separately from historical entries.
Older pages retain a fixed world identity and sequence boundary; **Refresh journal**
starts a new view that includes later changes. The UI identifies its coverage
boundary, marks committed evidence by sequence, and displays recording times.
Changing places discards the previous selection's entries. Late responses from a
previous world are ignored. Reads do not change state, start a game, call a model,
or inspect private trainer saves, party data, credentials or arbitrary module state.

The place selector is capped at 100 entries and reports truncation. Journal pages
contain 20 events, with bounded terrain previews. Full raw evidence remains in the
existing history API. This launcher slice gives players visible world continuity;
it does not add native in-game journal rendering, a complete trainer-save decoder,
or a proof of long-running multiplayer gameplay.


## Confirmed cooperative outcomes

Guild expeditions and meetups already have server-owned completion rules and
persistent guild XP. The authority can now record these real outcomes in the
same SQLite transaction as the existing completed flag and reward. This is not a
model declaring that a quest succeeded because it saw suggestive dialogue.

Because guild destinations and activity are group-scoped, recording is **off by
default**. The guild leader explicitly chooses:

```text
/guild chronicle on
/guild chronicle off
/guild chronicle
```

Turning it on publishes future aggregate completions to shared world history and
the builder's context: the guild name at the time, canonical map/place, goal type,
credited count and actual awarded guild XP. It does not publish member names,
private chat, boards, trainer saves, battles, catches or native quest flags.
Turning it off stops future publication; existing history is not erased. Enabling
it does not backfill earlier outcomes. Disbanding clears the publication setting,
so a new guild cannot inherit an old guild's consent.

The existing `/guild expedition start MAP COUNT` and `/guild meet start MAP COUNT`
commands and gameplay rules are unchanged. Expeditions credit distinct visits;
meetups require enough current members with fresh ready presence at the same map.
Completion and the awarded guild XP are authoritative. The travel input remains
authenticated **client-reported** presence, not server-simulated movement or an
anti-cheat guarantee. XP in history is the actual award, including the existing
cap, not a guessed nominal reward.

A failed history/index write rolls back completion, the visit that would complete
it and its reward. The next valid presence report can retry; duplicate reports
after successful completion cannot award or record it again. Explicitly starting
a new goal after completion creates a new occurrence. Restart retains both the
reward and its evidence. Cancelled, incomplete and opted-out goals do not become
shared completion records.

The existing place journal, recent GM context and older-evidence recall consume
these events. A deterministic controller experiment authenticates two trainers,
completes a real two-visit expedition through the normal STATE handler, confirms
the awarded XP, buries the event under unrelated changes, restarts, and proposes
an expedition marker from that exact evidence. It writes the ordinary GM proposal
but deliberately rejects deployment in the fixture. It proves the outcome-to-
context-to-proposal path, not a live model call, sandbox acceptance or native
rendering of the marker.

```sh
PYTHONPATH=test/world:. python3 -m unittest test_guild_world_memory -v
```

Publishing a completion does not itself authorize or trigger a new world edit.
The existing explicit GM requests and configured runtime purposes still govern
when a proposal is made. The completion is durable evidence for that work.

The actual mechanic-sandbox experiment was also attempted using the same real
completion and proposal flow. Bubblewrap failed while creating its NETLINK_ROUTE
socket with `Operation not permitted`. The candidate was rejected and no marker
was installed. No unisolated fallback or retry of that denied operation was used.

## Continuing dormant places

The archive already retains multiple generated templates and per-revision terrain,
but the native multiplayer protocol has one globally active generated template.
`_replace_cave` rejects a different template while any trainer occupies a generated
map. An atlas or link table alone cannot turn that slot into simultaneous regions.
This iteration preserves that barrier instead of presenting metadata as working
portals.

The builder's recall now includes matching **current archived revisions** by
literal label or selected stable place ID. This includes dormant destinations and
multiple saved revisions of the same place. It exposes exact revision, place ID,
label, active status and terrain revision, plus a read-only detail request. This
also works for archives predating history coverage without inventing their past.
No newest-by-timestamp guess silently selects a version to restore.

`captured_at_seq` distinguishes current archive facts from a historical recall
cutoff. The GM rejects mismatched current archive/inspection boundaries. Selection
is bounded to eight revisions with an explicit `has_more`; the full catalog has
keyset pagination. These are live current-state pages, not a frozen historical
catalog. Literal matches are not exhaustive semantic place discovery.

```sh
python3 -m world.world_memory saved-places --admin-socket /path/to/admin.sock
python3 -m world.world_memory inspect-saved-place --admin-socket /path/to/admin.sock --revision CONTENT_SHA256
```

The detail command checks the stored content digest, reads the saved base grid and
its own persisted terrain overrides, and links to that logical place's history.
It neither switches areas nor exposes trainer saves. Existing exact-revision
activation remains the only restore path and retains its multiplayer checks.
The builder can refer to a preserved destination in dialogue or a continuation
proposal without claiming a player visited it or a portal already connects it.

Tests preserve a harbor and its revision alongside a forest through restart,
inspect both dormant versions without changing the active world, reject activation
while occupied, and restore the chosen old version. A garden's terrain survives
another area's activation and is inspected/restored by its exact revision. A real
GM-controller fixture feeds a dormant harbor into a deterministic archivist proposal;
deployment is intentionally rejected, not reported as sandbox or native success.

A future simultaneous-region slice needs explicit per-player region/revision
identity, region-scoped NPC/terrain replication and native transition negotiation
before adding traversable connections. That protocol/native change is outside this
history patch. The world does not yet support simultaneous persistent generated
regions, cross-region portals or automatic agent expansion into new regions.

## History-informed edits that actually commit

`world.continue_area` connects the existing tool-disabled cave author to the
existing persistent event-area geometry editor. It is an explicit owner command,
not an autonomous background trigger. It edits the **active durable v9 event
area**; it does not silently activate another saved place or replace its template.

```sh
# Uses the existing pinned Codex author. The request and shared geometry/history
# go to that model provider; ordinary model usage charges may apply.
python3 -m world.continue_area --admin-socket /path/to/admin.sock --request 'Restore the refuge clearing using its recorded terrain history'
# Explicitly allow the new proposal to be committed if authority checks pass:
python3 -m world.continue_area --admin-socket /path/to/admin.sock --request 'Restore the refuge clearing using its recorded terrain history' --apply
```

Without `--apply`, the result is a structurally checked proposal, not a committed
edit or a promise of connectivity validation. Running again with `--apply` authors
a new proposal against freshly inspected state; it does not approve a previously
printed proposal verbatim. The author emits only 1..64 inert tile edits and references
to original recalled history sequences. No generated Python is executed. Unmentioned
tiles stay unchanged, including other builders' work. Player names, private intentions,
native saves and per-trainer event state are excluded from the author context.

On apply, the existing authority checks the exact world UUID and terrain revision
under its lock, then runs its existing protected-cell, character-access and connected
land checks. Occupied-area and connection-capacity barriers remain intact. An edit
and its `terrain_changed` history record commit in one transaction. That record now
can carry the original `history_evidence` sequences that informed the design. These
references establish provenance, not proof that a model's interpretation is correct.

The template hash and logical place ID remain unchanged, so this geometry-only path
does not reassign native story keys or create another story-progress slot. Existing
clients receive the established reset/terrain negotiation. The command reports the
authority commit acknowledgement and delivery counters, not native rendering or
per-client acceptance. Never blindly retry an uncertain transport failure after apply;
read current history and terrain first. No automatic retry is implemented.

Five focused tests use the real admin dispatcher and SQLite transactions: restore a
clearing from its original terrain history, retain the same place/template through
restart, verify both authenticated clients receive reset and the new terrain revision,
reject a concurrent edit and an occupied area, and roll back on history persistence
failure. Preview/private-data and invalid/protected-cell cases are included. The final
aggregate has 107 passing Python tests. This is a deterministic author fixture, not a
live model/provider call or native playthrough. Native build/headless remain blocked by
missing png.h and the resulting absent binary. No live world was changed.

## Build a new destination from a recorded outcome

The existing `world.author_cave` command now accepts `--world-history` with an
explicit admin destination and optional `--label`. It retrieves matching public
history before calling its existing tool-disabled author. Existing cave, wildlife,
shared guide and cast modes keep their production compilers and validators.

```sh
python3 -m world.author_cave 'Honor the Redwood expedition with a refuge' \
  --admin-socket /path/to/admin.sock --world-history \
  --label 'Redwood Refuge' --shared-guided-wilds
```

This is an explicit generation **and publication** command using the provider's
normal model usage. Matching public history and the design request are sent to
that provider. Private trainer identities, saves, party hashes and intentions are
not included. Without the new flag, the existing author workflow is unchanged.
History-aware publication requires the persistent generated-area archive.

The compiled destination activates only if the same world and event sequence
still match the inspected context, while holding the authority lock. Existing
occupancy and connection-capacity checks still apply. A concurrent world change
rejects publication rather than using a stale historical picture. There is no
automatic retry. The activation event retains the sequences supplied to the author
as `history_evidence`; these are context provenance, not a claim that the model
relied on every record or interpreted them correctly.

A genuinely new template receives its own stable place ID and the earlier place
remains in the archive. Identical content retains the existing content identity;
the system does not fabricate a distinct place just because a model returned it
again. Naming does not establish lineage. This workflow creates a new destination,
whereas `continue_area` edits the existing place without changing its story key.
It does not create portals, run both regions simultaneously or record a player visit.

The end-to-end fixture completes an opted-in guild expedition through the real
guild authority, feeds that recorded reward into the real author/compiler flow
with a deterministic provider response, and publishes a named guided refuge.
The guide's actual encoded dialogue references the completed goal. Restart keeps
the new template, stable identity and evidence; the old camp can still be restored.
A concurrent rename rejects publication and leaves the original world intact.
This is not a live provider call or native game acceptance.

Expanded validation ran 154 checks: 150 passed, while four existing native guide/
cast compilation fixtures failed because their compile environment could not find
`pokemon.h`. No native source was changed in this iteration. The full native build
also remains blocked by missing `png.h`, and headless has no resulting executable.
Python compilation and whitespace validation pass. These limits are not reported
as passing native tests.
