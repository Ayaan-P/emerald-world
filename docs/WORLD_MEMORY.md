# World memory: build on what actually happened

## Current implementation target and verification

The app authority, persistent history and REGION1 reference client live in this
repository. The actual RC10 Expansion port lives in the separate engine fork,
branch `dot/world-memory-regions`, based on published checkpoint `2c3d08f42` and reconciled with `c8feb78c`
(co-op pending-presence, battle-entry and native block scheduling fixes).
The app gitlink and builder pin both select
`db028d31a8e4fcb615e60414c7a870cba3263330`.

The Expansion WORLD menu can browse four owner-opened immutable caves per page,
select a destination after releasing field ownership, then enter through the
existing manual generated-area action. Selection never warps automatically.
The bridge preserves CAVE16/RULES3 negotiation and makes the menu independent of
chat support. It does not add seamless portals, mutable regional wildlife/story
state, or persistent selected-region resume in a trainer save.

`engines/expansion.mk` now passes `GENERATED_WORLD_REGIONS`, defaulting to zero.
The port remains opt-in pending full native acceptance. Two compiled tests of
actual Expansion bridge functions and one compiled actual WORLD menu fixture
pass. Field/render backends are instrumented; this is not a linked engine build
or a two-client playthrough. The full build attempt stopped before compilation
because the shell could not authenticate the submodule clone. Exact source files
were retrieved using the GitHub connector, without substituting an older engine.

The earlier outer `src/platform/` changes and fixtures remain reference-engine
work only. Their CAVE10 fixture does not validate Expansion. No release artifact,
live world, integration branch, merge or deployment is changed by this draft.

### Public place catalog

Authenticated REGION1 clients may send `REGION LIST <offset>`. The authority
returns BEGIN with offset, count and next offset, at most four PLACE records
(logical UUID plus a hex-encoded 20-character display label), then END. Only
owner-opened pinned destinations are listed; no party, save or private chat is
included. Listing does not alter admission. Names are display hints, while UUIDs
select places. Pages reflect the current catalog, not a historical snapshot.

## Decision and first slice

A persistent world needs a memory of its places and changes, not a second save
format and not a story that a model invents after polling. Keep `world.sqlite3`
as the authority, keep native trainer saves private, and give the next builder a
bounded, readable view of confirmed history alongside the current world.

This candidate starts from RC10 app checkpoint
`d03b4f668d5d8e1ac388341e9d8d0cad407f69ad` and incorporates published app source
handoff `53c87d64`. The later opt-in native port updates the Expansion pin as
described above; it does not merge wildlife experiments or change a running world.

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

## Connected-place investigation: verified native boundary

The four isolated native guide/cast fixtures above had stale temporary header
stubs after RC10 added `GeneratedMap_HasUsableParty`. The repository does contain
`include/pokemon.h`; the full-game include tree is deliberately not used by these
small C harnesses. A shared party-API fixture now supplies the missing API and a
usable party, and the four native harnesses explicitly verify that an empty party
still blocks entry. They execute real `generated_map.c`, and the shared versions
also execute extracted production `CaveLine`/`CavePump` logic. All 154 checks now
pass, including those four native component tests. This does not fix the separate
full-game libpng build dependency or constitute a full game playthrough.

The component tests confirm safe template staging, actual generated-map entry,
return to the original native map, reconnect handling, refusal to overwrite a
prepared area, and staging a new guide/cast only after leaving the old one.
They provide a useful baseline for region transitions. The current implementation
still has no connected-region feature.

Concrete integration points and minimum implementation boundary:

1. `world/server.py` owns a single `shared_cave`. `CAVE GET/ACK`, STATE admission,
   `_snapshot`, `_link_presence`, `_link_line` and terrain/event commands all assume
   that global identity. A region-capable authority must resolve an immutable
   revision and terrain from the connection's admitted logical place, rather than
   temporarily switching this global field. Presence and link sessions must be
   scoped by both logical place and revision, even when native map numbers match.
   Otherwise players in different places can see or battle each other accidentally.
2. `world_places` records lineage but does not select a canonical current revision
   per place. A real region activation record must explicitly pin each place's
   served revision. Named links must target stable place IDs and an explicit
   entrance, not labels or incidental template hashes. Adding these records alone
   is not traversable travel and should not be exposed as completed gameplay.
3. `src/platform/world_bridge.c` has one negotiated cave identity per client,
   which is enough for one client occupying one region. Its mismatch recovery
   already leaves a prepared map before staging another. Region transitions need
   a new capability-negotiated request/acknowledgement tying the source admission,
   destination and immutable transfer together. Old clients must retain the old
   default area and never receive transition verbs they do not understand.
4. `src/platform/generated_map.c` keeps one `sPrepared` layout and one `sReturn`
   overworld warp. `GeneratedMap_Enter` requires a safe outdoors/on-foot state,
   usable party and acknowledged template; `Leave` returns to the preserved native
   warp. A real inter-region transition must preserve that original return anchor
   across the whole journey, end interactions before transfer, install the new
   template only outside the old prepared state, and then validate a destination
   landing. Calling Enter from inside, clearing sPrepared early, or pretending a
   link table is a warp bypasses those safety properties.
5. The first complete playable slice should use two immutable plain generated
   places and one bidirectional entrance, with a third client remaining in the
   first place. Test peer isolation, co-op refusal across regions, same-region
   co-op, stale acknowledgements, disconnect recovery and original-overworld
   return. Only then add mutable event-area terrain, whose commands currently
   address the global active template, and whose private trainer progress must
   stay out of shared history. Existing finite native story slots remain a
   separate continuity limit.

This crosses authority admission, replication, link-session isolation, native
field transitions and save return semantics. It is not safely completed by a
server-only link patch. No such half-integrated route was enabled here. The
repaired native component harnesses remove one verification obstacle; full
native build/playthrough and the coordinated region protocol are still required
before claiming connected persistent places.

## Implemented REGION1 authority/admission slice

The first stage of the connected-place architecture is now implemented, rather
than only described above. It is experimental **server and reference-client
support**, not native connected-region gameplay or a portal system.

An owner opens an archived immutable plain cave with the existing admin socket:

```python
from world.client import admin_request
region = admin_request('', {'command': 'open_region', 'revision': content_sha256},
                       admin_path='/path/to/admin.sock')
# Keep the returned place_id. Opening does not replace the legacy default area.
```

`world_region_revisions` pins one revision per stable place. The pin and a public
`region_opened` record commit together; reopening is idempotent. Another revision
of that logical place cannot silently replace it. This stage supports EWGMAP01
only. Mutable event/wildlife/guide/cast regions are not admitted through REGION1.
Their legacy default-area workflows continue unchanged.

A compatible presence client adds `REGION1` after its cave capability and before
any RULES suffix, for example `SOCIALCAVEREGION1`. Only that client receives
`REGION READY 1`. After reporting a fresh ready position outside generated maps,
it can send `REGION SELECT area:UUID`. The authority checks the owner-opened pin,
source occupancy, active tag/link/rally activity and archive digest, then returns
`REGION SELECTED area:UUID CONTENT_SHA256`. The client must still perform the
normal CAVE GET/hash validation/ACK exchange before any generated-map STATE is
accepted. There is no automatic teleport or claim that a player traversed a link.

`world.client.RegionClient` implements this capability and the bounded template
verification/acknowledgement path. Its `select_region(place_id)` returns the exact
validated template; it never invents movement or calls native warp functions.
It accepts snapshots interleaved with protocol responses. Integration tests use
this actual client and the actual authority dispatcher over in-memory wire I/O.

Each selected connection retains its own immutable template independently of
`shared_cave`, which remains the legacy default. STATE collision/admission and
peer snapshots use the selected revision. Same native map numbers are no longer
enough to place two regional clients together. Internal link presence includes
an authority-only region scope, used by offer, accept/readiness and tag range
checks; the native seven-field STATE and existing link payloads do not change.
Cross-region co-op is refused, while same-region tag consent and co-op admission
use the existing coordinator. A pending or active tag/link blocks reselection.

Default-area replacement and terrain edits do not reset or block on pinned
regional occupants. Client selection is session-local: reconnect negotiates from
the default until a region-capable client selects again. The region pins and
layouts persist, but this is not a new trainer save/resume mechanism. Inspection
now associates generated-map player reports with their admitted place/revision,
so history recall need not mistake another region for the default. No player
arrival event is synthesized from selection or client-reported STATE.

Five integration tests cover three clients in two simultaneously occupied places,
same-region visibility and tag/co-op admission, cross-region isolation, independent
collision geometry, departure/reselection while another client remains behind,
refusal while inside/busy, untouched legacy negotiation, durable pins, idempotent
opening, and default event-area edits while a pinned plain region is occupied.
The final expanded aggregate passes **202 checks**, including native component
coverage. The standalone Unix-socket test was attempted separately and is blocked
at socket creation by `Operation not permitted`; no socket/WAN claim follows from
the in-memory integration. The full native build still requires missing png.h.

Still required for playable connected places: native REGION1 negotiation and
selection UI, source-to-destination transition state machine preserving the
original overworld return anchor, persistent route/landing definitions, and
full native playthrough. Mutable event-area region scoping remains out of this
stage. No portals, automatic travel, live-server migration or deployment are
claimed or enabled.

## Opt-in native region selection and admission

The native bridge now implements the next stage behind
`GENERATED_WORLD_REGIONS=1`. The default remains **0**, so existing ordinary
builds and legacy HELLO messages are unchanged. This flag is added only to the
portable/native build flags and requires generated maps. It has not been enabled
for a release or deployed to a live world.

```sh
make -j2 linux CFLAGS=-g WERROR=1 GENERATED_WORLD_REGIONS=1
```

For an interactive chat-capable build, the owner first opens a persistent plain
region through `open_region` as above and gives the player its exact place ID.
The player returns from any generated area, opens world chat, and types:

```text
/region area:00000000-0000-0000-0000-000000000000
```

Replace the example with the actual owner-provided place ID. This is intercepted
locally, never broadcast as a chat message. Close chat so the normal overworld
presence becomes ready. The bridge sends a fresh STATE before the one-shot region
selection request, verifies the matching place/revision response and reuses the
existing cave reset, transfer, content validation and acknowledgement pipeline.
While selection is pending, generated-map entry is blocked. Once chat status says
`region ready: use WORLD`, the player uses the existing WORLD generated-area
entry action. Selecting alone does not warp or alter a save.

The existing `GeneratedMap_Enter` usable-party, field, template and return-position
checks remain intact. Leaving uses the same original native overworld return
anchor. A player must leave before choosing another region; this stage does not
implement a seamless cave-to-cave transition or a route/portal graph. Server-side
busy/occupancy checks still decide whether selection is allowed. A refused
selection leaves the prior admission available. An expired request that was never
sent is cancelled locally; an unanswered sent request disconnects instead of
retrying or guessing which template the authority selected.

Capability rejection falls back to the prior cave role before downgrading its
cave/Expansion capabilities. The compiled negotiation test explicitly preserves
`CAVE10` when `REGION1` is unsupported. Unexpected or mismatched region replies
are not accepted. Disconnect clears pending selection; no trainer save contains
or is rewritten with region selection state.

Current UI scope is **interactive chat-capable clients only**. The existing
Windows and headless paths disable chat, so this command is unavailable there
even if the native bridge can negotiate REGION1. There is no claim of a Windows
or headless selection menu, and no hidden alternate UI is provided. The protocol
reference client remains available separately.

Two new compiled C tests exercise production `RegionQueue`, `RegionPump`,
`RegionLine`, cave transfer/acknowledgement functions, chat interception, capability
fallback and actual `generated_map.c` entry/leave. Two independent component runs
consume distinct region frames produced by the actual authority. They verify no
warp before explicit entry, correct staging/acknowledgement, empty-party refusal,
unchanged native return coordinates, refused/mismatched replies and timeout behavior.
The field/task/warp-execution shell and fresh-state emission are fixture stubs,
not two running graphical games. The full expanded aggregate passes **204 checks**.

Full native build with the flag was attempted and is still blocked by missing
`png.h`; headless cannot run without the executable. Unix sockets remain blocked
in this execution environment. No full Expansion build, two-native-client
playthrough, graphical rendering, WAN session or seamless portal acceptance is
claimed. The offline XL progress system is separate; this plain-cave selection
path does not migrate private story flags, event graphs or finite progress slots.

## Custom terrain-aware routes (independent generator)

`world.route_landscape` accepts a bounded original plan of arbitrary landmark
clearings, rectangular terrain reservations, a seed and up to four alternate
routes. It builds a spanning route network using deterministic A* around the
reservations. Extra routes must carve new terrain outside the endpoint clearings;
they cannot simply claim that an existing path is a new loop. Plans that separate
required landmarks fail instead of erasing reserved terrain.

Run `python -m world.route_landscape plan.json area.ewmap --report routes.json`.
The plan has exactly `seed`, `landmarks`, `reservations` and `loops`. Landmarks
have unique lowercase `id`, integer `x`, `y` and `radius` (2..10). Use 2..12
landmarks inside the 127-square map, leaving the native entry at (1,1) and exit
at (125,125) available. Reservations are [x,y,width,height] rectangles inside
the perimeter. Outputs must not exist. The report contains measured paths,
newly carved tiles and the actual content revision, not authoritative history.

This emits the existing EWGMAP0A format and reuses native validation and ordinary
owner publication/persistence. It does not create a new region registry or save
system. The CLI only writes local requested files; it does not contact a server.
A generation report is not proof of publication. Reserved terrain uses existing
impassable XL graphics, not new biome artwork, water simulation or licensed
assets. Native entry/exit, quests and inter-map portals are unchanged.

This generator uses the existing single active XL publication path; it does not
extend outdoor regional admission. The generator and existing authority persist
its geometry and logical place identity across restart in component tests. Full
native playthrough remains outstanding.

### History-informed route author

`python -m world.author_routes 'A mountain divide with an orchard and lookout' --output new.ewmap`
uses the same version-pinned, tool-disabled author adapter as `author_cave`.
The provider returns only the route plan schema, compiled and validated into
ordinary XL geometry. The theme is sent to the provider and usage may be charged.
Add `--history-socket /path/to/admin.sock` to read matching public committed
history for this offline proposal. Trainer observations and saves are not sent.

For explicit shared activation, use `--activate-shared /path/to/admin.sock
--label 'Orchard Divide'` instead of `--output`. This requires persistent area
archiving and automatically recalls history from that same authority. Publication
uses its existing world/sequence guard, archive and occupancy checks. Old places
remain archived; a concurrent change rejects activation rather than overwriting
new activity. A committed activation cites the recalled sequence evidence. This
records provenance, not proof that a model's narrative interpretation is true.

This activates the existing single shared destination slot. It does not extend
regional admission to outdoor maps, add portals, or connect canonical regions.
Compatible native XL clients are still required. Tests exercise actual authority
persistence and validation with deterministic fake provider responses, not a paid
model call or linked native gameplay session.

### Characters at generated landmarks

`world.route_characters.bind_landmarks(character_plan, blob, route_report,
chapter_landmarks)` binds each active chapter to a named clearing from the route
report. It returns an ordinary validated character plan with the exact XL content
revision and generated-map coordinates. It does not deploy a mechanic or replace
a map. The existing character compiler, staging and authority checks still apply,
including joint NPC collision validation so characters cannot seal a route.

The integrated fixture follows a real public expedition outcome through route
authoring and shared activation, places a researcher at camp, authenticates a
client and challenges that character, then uses a later committed guild meetup to
motivate an authored move to the lookout and a new team. Restart preserves the
map, character and evidence. Model output and sandbox execution are fixture
boundaries; the reducer, authority commits, authentication and scoped wire are
exercised. Team evolution is authored fiction, not proof of a battle or catch.

The paired draft pins the CHARREG1 engine at `80bf5672c7caa43c39888007300683519bcd7fbb`.
The existing XL feature cohort enables shared-slot character scope;
`GENERATED_WORLD_REGIONS` remains opt-in and is not needed for shared XL NPCs.
Neither this fixture nor a matching wire response proves a linked native gameplay
session. Outdoor multi-region selection remains outside
this slice; archived characters appear only when their exact shared map is active.

Paired-source verification reconstructed the complete engine tree and matched
`326d99cbef8e48d241343024ee8be5c6587abe19`, the published tree for that pin.
The local reconstruction's commit metadata is not a clean pinned submodule;
source-tree equality is the verified result. An actual native build stopped at
`tools/gbagfx` because `png.h` is missing; SDL2/libpng development packages are
also unavailable. No linked binary or two-client playthrough is claimed.

### Frontier outpost construction

`python -m world.frontier_outposts camp.json --admin-socket /path/to/admin.sock
--label 'Western Frontier Camp'` previews an additive construction plan in the
active plain XL map. Add `--apply` to commit it. A plan contains exactly `x`, `y`,
`width`, `height`, `gate` and `reservations`. For example:

```json
{"x":15,"y":20,"width":9,"height":7,"gate":"west","reservations":[]}
```

The bounded footprint becomes a walkable courtyard with one gate. An access trail
connects that gate to existing land. The perimeter and a rock buffer remain
impassable, and every old walkable tile is preserved. Width and height are 5..15;
gates face north, east, south or west. Construction rejects overlap with old
routes or sites, excessive trail length and unreachable locations. Reservations
use [x,y,width,height] rectangles; carry forward the source plan's reservations
when they must remain protected. Arbitrary terrain bytes do not encode ownership
or protected-land semantics, and the tool does not infer them.

The owner-only `construct_outpost` admin command compiles against the exact active
archived template while holding the authority lock. It requires the inspected
world ID, sequence and previous revision. Existing publication occupancy and
persistence checks apply. The new map continues the same logical place and its
ordinary committed activation history; both versions remain in the archive.
Restart and revisiting preserve the construction. A stale or duplicate request
fails rather than applying twice. Placed persistent characters on the shared revision are rebound at unchanged
coordinates, with the complete NPC collision set validated against the new map.
Their identities, teams, versions and prior history remain unchanged. Private
player progress is not migrated by this tool.

This is an owner/agent construction primitive, not a player crafting economy,
settlement simulation, indoor building system or new tile-art pack. Walls use
the existing impassable outdoor tiles. It adds no autonomous construction trigger
and changes no engine source. Tests cover additive geometry, reservations,
place continuity, archive/restart, failed commits and source-extracted native XL
staging. The native-source test skips when the paired source is unavailable.
The exact 80bf567 engine staging function accepted constructed geometry and
rejected damaged bytes locally. A full native build stopped at missing `png.h`;
headless smoke could not start because no binary was produced. A linked native
playthrough and rendered building appearance remain unverified.

Design precedents informed the narrow scope: Valheim documents persistent shared
worlds (https://www.valheimgame.com/support/a-guide-to-dedicated-servers/), while
Factorio's elevated infrastructure changes traversable geography
(https://factorio.com/game/content-space-age). This implementation reuses the
existing authority and native geometry rather than adding another world store.


Construction now commits geometry, unchanged-location character bindings and the
corresponding mechanic source atomically. A bounded wrapper around the existing
authored reducer preserves those exact bindings on subsequent ticks and after
restart. A later chapter that moves an actor within obsolete geometry fails
rather than silently transporting it; author that chapter against its current
revision explicitly. Repeated construction composes wrappers without replacing
character chapter state or fabricating a character evolution.

Pending mechanic/deployment work and character battles block inhabited
construction. Characters on opened immutable regions cannot be migrated through
the shared slot. Other revisions' actors remain untouched. Old archived geometry
remains available, but migrated actors appear only on their new exact revision,
not simultaneously on old copies. A committed placement-change record connects
the previous and new geometry while preserving earlier history.

Tests include the actual authored chapter reducer across construction, repeated
construction and restart, exact-revision authentication/challenge wire, unrelated
actor isolation, an NPC blocking the newly added access trail, and rollback after
a module-write failure. Test source execution uses a fixture boundary; production
retains the existing sandbox runtime. Full native rendering/playthrough limits
above still apply.

### Outcome-grounded inhabited settlements

`python -m world.author_settlement 'Honor the expedition with a field station'
--admin-socket /path/to/admin.sock --outcome-seq 42` asks the existing tool-disabled
provider for an inert settlement proposal and previews it. Add `--apply` for
explicit publication. The selected sequence must be a real committed public
`guild_goal_completed` event. Theme, archived geometry and that public outcome
are sent to the provider; trainer names, private saves, party hashes and live
inspection data are not. Calls may incur provider usage charges. Recorded text
is treated as data, not instructions.

A plan contains `label`, the existing `construction` footprint, and one
`resident`. Resident fields are `id`, `name`, `role`, `goals`, `team`, `gfx`,
`text`, `offer`, `completion_text` and `completion_goals`. The offer uses the
existing expedition schema. The compiler places the steward at the courtyard
center and creates ordinary validated character chapters: arrival with the offer,
then updated goals/dialogue after that exact character/offer revision completes.
The team stays unchanged. Construction is authored fiction inspired by evidence,
not a claim that the guild constructed a building or the steward won a battle.

The owner-only `found_settlement` command also accepts an already-authored inert
plan directly. It stages and runs the compiled source through the existing
kernel-sandboxed mechanic runtime asynchronously. A failed stage changes no map
or actor state. After staging, world sequence, map revision, source and occupancy
are checked again. Geometry, source, character state and bindings then commit in
one transaction. Existing inhabitants are preserved through the continuation
mechanism above. The normal capacity, character-transition and joint collision
validators remain authoritative. A duplicate resident ID fails rather than
replacing an established character.

A visiting guild leader sees an ordinary revision-scoped character offer. It
requires explicit native acceptance and prior chronicle opt-in; merely founding
the settlement never starts an expedition or enables publication. The existing
guild authority records completion, and the normal character reducer changes
this steward's dialogue and goals. Restart retains both the settlement and the
completed character state.

The end-to-end tests substitute provider output and sandbox execution, but use
real public guild outcomes, geometry, authority transactions, authentication,
scoped offer consent, expedition completion and the authored chapter reducer.
No actual model invocation is claimed. An actual sandbox stage was attempted in
this environment and failed because bubblewrap could not create a NETLINK_ROUTE
socket. The real authority returned refusal with the map unchanged and steward
absent. No weaker execution route was used. Native build/rendering limits above
also remain; these protocol/component tests are not a linked gameplay session.

### Private landmark surveys

After publishing a route template, the owner can register the same route plan:
`python -m world.landmark_survey plan.json --admin-socket /path/to/admin.sock`.
Registration recompiles the plan, requires byte-for-byte equality with an archived
XL template, and fixes its named clearings for that revision. It does not activate
or modify terrain. Only this owner-admin path can register surveys.

Inside that acknowledged map, a player types `/explore start` using existing
native chat. `/explore status` shows progress and the nearest undiscovered
clearing's coordinates; `/explore stop` pauses it. Reaching within one tile of a
clearing center records a discovery and sends a private chat message. All
landmarks can be explored in any order. Completion and partial progress survive
server restart. Starting again resumes that revision, while starting in another
registered map selects its separate progress.

This is opt-in personal exploration, with no rewards or anti-cheat claim.
Validated client-reported presence is the evidence, not a server simulation of
travel. Trainer discoveries stay out of public world history and model context by
default, and other players do not receive the private messages. Old-revision surveys pause when
the map changes; reactivating the exact archived map allows them to continue.
Landmarks are coordinate destinations in existing geometry, not new sign art.
Clients need their existing interactive chat path; this adds no Windows/headless
chat UI and does not change native region admission.

A player can deliberately share one discovered landmark while standing beside it:
`/explore share camp` previews the public data and permanence. Only
`/explore share camp confirm` publishes. The public record contains the landmark
name, coordinates, exact map revision and durable place identity, not the player's
name or other discoveries. This permission applies only to that arrival, not
future surveys. The shared discovery can be recalled by landmark name and used
as evidence for later authored destinations. It confirms consent and validated
client-reported presence, not independently simulated travel. Repeated sharing
of the same landmark/revision reuses its existing milestone. Publication and its
receipt commit together; failed writes leave the private discovery intact.

The end-to-end fixture follows an authenticated survey arrival through explicit
sharing, public recall and the existing guarded route-author publication. The
new destination cites the shared event, and the receipt survives restart. Model
output is a deterministic fixture; this is not an automatic world-building
trigger or proof of a live model/native game session.

Native compatibility privacy boundary: updated outer native clients gate public
`/explore` commands at `WorldBridge_ChatSend`, not only the composer. The first
attempt sends only the fixed harmless `/explore protocol 1` probe and retains the
private draft. A dedicated sequence-matched authority response enables commands
for that connection; the player must submit again. Old servers may broadcast the
probe, but never receive the held discovery command from this updated client.
Chat messages cannot masquerade as protocol readiness. Disconnect and reconnect
clear support, and an unanswered probe never releases a queued private command.

This does not protect older clients or arbitrary custom clients. Those clients
can expose slash-command text on old servers. The paired draft now pins actual
Expansion guard commit `1b34f4360bf8248a337c024acbc68b238bebf738` in both
the gitlink and build script. Its bridge and composer sources match the published
engine files. This pin includes the privacy guard, not unpublished character
walking. Explicit public-discovery confirmation remains required after capability
negotiation. Production source fixtures and object compilation passed; a linked
build of this newer guard and live network acceptance remain unverified.

### Coastal route geography

Each route landmark can now specify `landform` (`round`, `lagoon`, `cove`, or
`headland`) and `facing` (`east`, `south`, `west`, or `north`). Defaults preserve
old round plans. Round radius accepts 2..20; coastal forms require 6..20. Centers
remain walkable for surveys and characters. Lagoon pools create a connected
shore circuit, coves cut an inlet through the clearing edge, and headlands taper
into narrow peninsulas. These are actual tile changes in ordinary shared XL map
bytes, using existing native grass and blocked water, not new elevation or art.

The route author receives this schema and may choose contrasting forms. The
compiler reserves their water cuts before route search: paths must go around
pools and inlets instead of filling them. Overlapping landmark footprints and
unreachable plans fail validation. Reports expose the exact protected water cells
for inspection; those cells are not an additional runtime state system. Reusing
this plan with surveys or settlement construction does not grant permission to
change an existing world.

Tests compare all twelve form/orientation combinations, check protected water
and landmark access, exercise constrained author compilation, and feed each form
through the actual Expansion C wire codec, including corruption rejection.
The codec test requires `EW_NATIVE_SOURCE` pointing at verified engine source.
Native rendered playthrough remains unverified; no bridge, elevation, surfing or
new biome-art behavior is added.

### Authored journeys, forks and mandatory passages

A route plan may now include `journey` with `connections` and `required`, and set
`loops` to zero. Connections are up to 32 distinct undirected pairs naming
landmarks or the reserved `entry`/`exit` endpoints. They must connect every site.
The agent chooses the adventure graph rather than accepting nearest-neighbor
connections. For example: entry → camp; camp → west and east; west/east →
sanctuary; sanctuary → exit. Adding camp → sanctuary requests a real shortcut.

The compiler routes these edges in declared order, with water separation from
unrelated corridors and clearings. Impossible crossings fail rather than adding
unrequested shortcuts. `required` names landmark clearings every entry-to-exit
path must pass through. After carving, the compiler removes each required
clearing in turn and searches the actual tile graph; a surviving bypass rejects
the candidate. In the fork example, camp and sanctuary can be required while
west and east cannot. This is geographic passage through a clearing, not a quest
lock, interaction requirement, or proof that the player spoke to an NPC.

The existing constrained author, archive, explicit activation and history guards
all apply. An integration fixture follows a voluntarily shared camp discovery
into a new fork/rejoin destination citing that public sequence. Actual native
codec tests include journeys containing each coastal landform and corruption
rejection. No new engine protocol, encounter table, reward or live trigger is
introduced. Native rendered acceptance is still separate.

Design inspiration: Dormans' distinction between mission structure and spatial
layout ([paper](https://pcgworkshop.com/archive/dormans2010adventures.pdf)), and
Red Blob Games' use of graph search for pathfinding and map analysis
([introduction](https://www.redblobgames.com/pathfinding/a-star/introduction.html)).
The implementation is original and intentionally limited to the game's existing
walkable-ground/blocked-water XL format. Existing custom wildlife tables belong
to other cave formats; this feature does not mislabel terrain shapes as new
encounter-bearing biomes.

### Authored XL encounter populations (CAVE17 candidate)

`world.author_routes --encounters` explicitly asks the constrained author for an
encounter population in addition to route geometry. The plan's optional
`encounters` object has `rate` (1..100) and exactly twelve `wildlife` entries,
each with an enabled Expansion species name and a level (1..100). Native slot
weights are 20,20,10,10,10,10,5,5,4,4,1,1 percent. The report combines repeated
species/level entries using those weights. Rate is a native encounter parameter,
not a promised per-step probability. No private trainer party is used to infer
levels, and this single population applies across the destination, not separate
per-landmark habitats.

The new immutable format is `EWGMAP17`, followed by 37 bytes (rate and twelve
little-endian species IDs/levels), followed by the existing 127x127 geometry.
Its digest covers the table as well as every cell. Only an explicit `CAVE17`
client receives `XLWILDLIFE` plus `CAVE WILD` and the rows. Older `CAVE16` clients
receive no map instead of silently discarding the table. Existing archive,
occupancy and history guards apply; changing wildlife changes the exact revision.
Surveys and characters bind to that exact immutable revision. Outpost construction
still rejects this format rather than erasing its encounter data.

Archive inspection and the active public context expose the bounded authored
population, clearly distinguished from observed wildlife, catches or player
progress. The history-informed author can use that public context when proposing
a subsequent destination. No automatic live-world update or battle outcome is
inferred. The native counterpart must be built and paired before claiming these
maps can be played; this candidate is an app/protocol extension, not evidence
that an older engine pin already supports CAVE17.

### Generated expedition destinations and authored wildlife

Generated guild expeditions now bind to an archived logical place and its exact template revision. `/guild expedition start here COUNT` uses fresh, authenticated, acknowledged generated-map presence, never a client-supplied destination identity. Native `GeneratedWorld_*` map aliases are rejected as ordinary expedition goals. Replacing the active shared template pauses credit for its old revision; restoring that exact revision makes it reachable again. Public progress keeps the place/revision context for subsequent character chapters.

The app also reconciles the published generated-character offer protocol: `PLACEQUEST1` plus `CHARQUEST1` negotiates a labeled destination and requires explicit acceptance through the existing character authority path. No automatic travel or world activation occurs. CAVE17 destinations require the distinct `cave_xl_wildlife` capability, not CAVE16 alone. Population bytes are part of the template hash, so changing only species/levels invalidates an old destination revision.

Validation includes actual app offer consent, authenticated arrivals, guild completion and restart for both plain XL and authored-wildlife XL, plus CAVE16 refusal and population-only replacement. These are in-process authority tests, not a live game acceptance run. This candidate deliberately retains the published privacy engine pin `1b34f436`; that engine does not include CAVE17 or PLACEQUEST1. Their app protocol paths are prepared and tested, but are not usable in that pinned game binary. Native wildlife publication remains blocked independently; no unsupported engine pin or walking implementation is included here.

### Recoverable authored route recipes

The route author retains the validated plan and derived compiler report. Shared activation sends a bounded version-1 artifact with the exact map bytes; the owner authority recompiles it and checks the report and revision, then archives it in the same SQLite transaction as map activation/history. A different artifact cannot overwrite that revision's original recipe. No model prompt, raw provider reply, recalled history, trainer identity or private progress is included. This checks reproducibility and archive integrity, not cryptographic proof of who authored a file.

After shared authoring, including after authority restart, register the saved landmark survey with:

```sh
python -m world.landmark_survey --revision EXACT_REVISION --admin-socket ADMIN_SOCKET
```

Registration reloads and validates the recipe against archived map bytes. It does not activate a different map, publish player visits, or start a player's survey. Players still opt in with `/explore start` after entering and acknowledging that revision. The integration test generates a provider fixture through the actual author command, publishes through the real admin dispatcher, restarts the authority, registers by revision, freshly authenticates/re-enters and records a private discovery. It is not proof of native in-place save/resume; normal play still leaves the generated map before saving and re-enters the archived revision after restart.

Offline output `route.ewmap` now also writes `route.ewmap.route.json`, which the survey CLI accepts after the matching map has been archived. Both paths are exclusive-create and never overwrite existing files. The recipe is written first: if writing the map fails, the durable recipe remains available for recovery rather than being silently discarded. The compiler format is versioned; a future compiler change that cannot reproduce old bytes must reject registration rather than reinterpret a stored route.
### Player-driven settlement growth

The existing opt-in GM runtime accepts `--settlement-growth-theme 'Extend the
surveyed frontier'` on its `run` command. This explicitly permits later eligible
steward completions to invoke the constrained settlement author and publish a
new inhabited expansion. Provider usage may be charged. The option is absent
by default. It shares the existing durable queue, runtime lock and minimum
author interval; no second background daemon or implicit provider is introduced.
Use `--no-events` if this runtime should react only to settlement completions
rather than also handling its existing selected-player event tasks.

The first enabled inspection establishes a baseline without authoring old
outcomes. Later genuine public completions must match the offer ID/revision of
a recorded settlement steward in the currently active logical place. Arbitrary
guild achievements do not trigger growth. Per-place cursors defer other archived
places instead of discarding their outcomes. A verified completion remains valid
if its steward is now away; publication still requires its logical place active.
Each founding stores an outcome receipt in the same transaction as geometry,
source, NPCs and history. An outcome can found at most one settlement, including
manual publication. Old camps without these new receipts are not retroactively
classified as automatic growth triggers.

Each selected outcome gets a stable world/sequence queue identity. Failed or
interrupted author/publication requests are terminal and never automatically
replayed. Omitting the growth option prevents queued growth work from running.
Re-enabling permits queued work, subject to a fresh exact-world/place check.
The authority again checks current geometry, occupancy and all existing staging
rules. Capacity limits surface in runtime status rather than invoking authors
that cannot add another character. A successful settlement publishes its exact
staged source reference back to the existing GM queue so later ordinary agent
work can preserve the newly inhabited world behavior.

The integrated fixture uses a genuine authenticated steward-offer acceptance and
guild completion, discovers it through the production authority query, and runs
the existing GM step through an authored second inhabited revision. It verifies
exactly-once consumption, restart, source continuity and no unrelated-place
leakage. Provider output and sandbox success remain substitutes. The actual
author adapter was separately invoked for preflight and refused this environment's
`codex-cli 0.167.0-alpha.4`, because its security-reviewed allowlist requires
`0.156.1`. The gate was not changed and no model call occurred. The previous
sandbox and native build blockers remain. Nothing here enables growth in a live
world merely by merging or starting the ordinary default launcher.

### Explicit settlement recovery

Growth failures never replay automatically. `python -m world.runtime_gm
retry-settlement --state-dir STATE --socket SOCKET --request-id ID` is an
owner-initiated reconciliation command. Stop the running GM first: recovery
holds the same exclusive runtime lock. It does not invoke the provider.
Status retains the original world, place, public outcome, attempted revision,
failure stage and previous attempts. Provider stderr is deliberately not saved.

The authority checks the atomic founding receipt first. A receipt reconciles a
lost success reply without creating another settlement. Without a receipt,
pending authority work remains uncertain and is not queued. A retry requires
the original world, place and exact revision, and the original public outcome
must still exist. The next explicitly enabled GM run checks that revision again
before provider invocation; normal commit guards and receipt uniqueness remain
in force. A changed place/revision needs deliberate owner handling rather than
automatic rebasing. Legacy terminal rows whose identities were overwritten
cannot be safely recovered by this command. No automatic replay or sandbox or
provider-version gate bypass is introduced.

Recovery validation: 125 focused tests pass, including receipt reconciliation
after an actual fixture-sandbox founding whose response is treated as lost,
pre-publication retries, pending-write deferral, wrong-scope/revision rejection,
and preservation of interrupted identity/stage. This does not establish live
model invocation or native gameplay; the documented runtime blockers remain.

### Survey and settlement draft reconciliation

This draft includes settlement growth and receipt recovery from frontier-outposts f09a52ad while retaining survey recipe persistence and the privacy-enabled native pin 1b34f436 in both the gitlink and builder. The initial reconciliation kept growth/construction format16-only. The subsequent encounter-preserving extension below adds format17 without downgrading its population. Terrain construction produces a new exact revision; old artifacts remain archived, and the derived exploration continuity described below applies only to verifiably unchanged sites. Native release integration remains separate.

### Encounter-preserving settlement construction

The app's outpost compiler, settlement author and opt-in growth consumer now accept format16 and format17. Construction changes only geometry: all 37 authored encounter bytes (rate and ordered species/level slots) are copied unchanged into the new digest-bound template. Owner inspection includes those ordered authored slots, and preview reconstruction must reproduce the exact archived revision before any plan is sent to the authority. Percentages are never used to approximate a table.

The existing guarded publication and character rebinding transaction preserves the logical place and migrates unchanged resident positions to the new exact revision. Archived old geometry remains available. Original survey recipes and arrival records remain bound to their original revision. Supported construction now creates a separately replayable derived artifact and carries only unchanged-site evidence as described below. Older CAVE16 clients still receive CAVE NONE for these maps.

Tests cover actual app author preview/publication, surviving prior residents, explicit NPC offer consent, guild completion, dialogue changes and authority restart while retaining every encounter byte. Constructed frames pass the actual local CAVE17 native decoder; tampered inspection slots fail their hash check. These are in-process authority and C component checks, not deployed gameplay. The pinned published engine remains 1b34f436, without CAVE17, and the native CAVE17 upload is still blocked. No denied native operation was retried.

### Exploration continuity through construction

For an authored route with a validated recipe, both direct outpost construction and inhabited settlement construction now archive a schema-2 derivation: parent revision, exact construction parameters, new revision, and a recomputable landmark report. Loading it replays the original route and every construction in order against archived bytes. This is a new recipe, not a relabeled old map or a claim that its original journey graph still holds. Legacy maps without route recipes remain supported for construction but cannot invent landmark ancestry.

Landmark IDs and centers survive. A landmark retains prior exploration evidence only when every tile in its radius-bounded square is identical before and after construction. A changed site's identity remains recognizable but requires a new visit; the new outpost gets its own stable named landmark and starts unexplored. Later construction applies the same check to earlier outposts. This is local landmark continuity, not a claim that the entire surrounding route is unchanged.

If the old survey was registered, the new survey and existing opted-in survey sessions advance atomically with map and resident persistence. Private inherited evidence points back to the original observed revision in a separate table. Original visit records are never rewritten, and inherited evidence does not create a current arrival or permit publishing a discovery without a real new-revision visit. The player's progress text explicitly distinguishes retained landmarks. Paused surveys stay paused; other players gain no progress. No discovery is automatically shared publicly. If the survey was not registered, the owner can register the derived revision later through the existing revision command.

Tests exercise both plain XL and CAVE17: explore a lagoon and camp, leave the map, construct a station that changes the lagoon but not the camp, restart/re-enter, retain only camp evidence, then discover the changed lagoon and new station. Actual inhabited-settlement authority commits, artifact tampering and failed persistence rollback are covered too. This is app-authority validation, not a new native save/resume or live multiplayer claim.

### Resident-authored private guidance

Persistent NPC chapters/actions can opt into `services: ["guide"]`. In a registered generated-map survey, a player standing adjacent and facing that resident can use `/explore guide NPC_ID`. The server requires fresh authenticated ready presence, exact acknowledged revision, the resident's explicit active service, negotiated generated-character support and the player's active private survey. It finds a shortest currently clear walking route over the actual archived tiles, avoiding resident and fresh ready-player positions. `/explore directions` refreshes up to three turns as the player walks; it does not move the player.

Guide targets and notes are private and survive authority restart. Already visited or validly inherited landmarks are not proposed as unexplored. Directions alone never mark an arrival, share a discovery, grant rewards or advance public history. Normal observed arrival records the discovery privately, and the separate explicit share command remains necessary for public character reactions. After terrain changes, old revision notes require asking a guide again; they are not silently retargeted.

This uses the existing protected `/explore` chat commands and published engine 1b34's CHARREG1 support on interactive chat-capable clients. It introduces no native walking, PLACEQUEST1 or CAVE17 requirement for plain XL guidance. App tests cover actual chat commands and tile-by-tile reported movement, privacy, explicit later sharing, restart, inherited evidence and unsupported-client refusal. Native rendered acceptance of this new guide interaction has not been run.


### Read the place's past while exploring

In an acknowledged generated XL destination, `/explore history` privately shows
three recent public records for that logical place. `/explore history older`
continues backward at the same fixed record boundary. Refresh starts at the
latest committed record. Earlier revisions are explicitly labeled as history,
not the current terrain. No survey opt-in or public discovery is needed merely
to read already-public history. `/explore` advertises the command.

The view includes recorded activations, names, authored character changes,
explicitly published discoveries and opted-in actual guild outcomes. Character
motives are labeled authored; guild XP is an authority award and travel remains
client-reported. Unknown event types have a generic description, never a raw
payload. Output is ASCII-safe and bounded to eight existing chat lines per page.
Private visits, trainer data, battle reports, prompts and arbitrary module state
are not exposed. Reading does not create world events, publish discoveries or
change survey progress. Replies go only to the requesting player.

Page cursors are connection-local and tied to world, logical place and exact
revision. Changing destinations or reconnecting requires a fresh history read.
A one-time projection repair indexes canonical place identities already present
in older character records; it does not rewrite events, dates or sequences.
This fixes previously missing resident stories in place-filtered history and
also makes them available to the existing place-aware retrieval paths.

Authority tests cover real discovery before/after explicit publication, actual
guild completion with publication off/on, committed character changes, restart,
old-index repair, unrelated-place isolation, fixed pagination and control-text
sanitization. This uses existing protected exploration chat commands, with no
engine pin, native movement or new artwork. Native rendered gameplay has not
been verified for this new command.


### Collective discoveries change a resident's role

An authored character chapter can now wait for `when: {"all": [condition,
condition]}` with two to four distinct public-event conditions. The existing
single-condition format remains valid. For example, a researcher can remain at
camp until players explicitly share both the orchard and ruins, then relocate
to the lookout with new dialogue, an authored team and the existing guide
service. The conditions may arrive in either order from different players.
This is an optional reusable authoring contract, not a globally installed NPC.

Partial matches are retained in the character's existing durable chapter state.
Only events newer than publication and observed while that chapter is a possible
next choice count. One event can satisfy at most one outstanding requirement;
replayed records never count twice. The first eligible completed branch wins and
discards other branches' partial matches. All matched original sequence numbers
become the changed character's public evidence. Offered guild outcomes still
require the exact character and offer revision; discovery conditions still need
the exact place, map revision and landmark. Private visits never enter this feed.

The native object relocation, dialogue, team and optional service are the same
validated chapter effects as before, not new engine protocols. The compiler
continues through the existing sandbox staging and atomic authority commit.
Agent context advertises the bounded conjunction. It does not automatically
author or deploy a character, relax validation, grant rewards, or infer battles
and catches from narrative team changes.

The integrated fixture uses two authenticated explorers, real private survey
arrivals and explicit sharing. A first public report persists across restart;
a second explorer's complementary report moves the researcher to the lookout,
changes dialogue, enables guidance and produces the new frozen challenge team
through the actual app protocol. Partial progress and replay do not grow the
team. The authored plan and successful sandbox execution are fixture boundaries;
no model call, native rendered session or live-world deployment is claimed.


### History-driven travelling casts

The GM can propose `{"character_ensemble": [plans], "tests": "Python tests"}`
for two to four new persistent residents in one publication. Every plan uses the
existing chapter contract. A caravan can begin away, arrive together when an
explicitly shared route report is committed, offer a guide and a distinct field
challenger at separate positions, and move its camp after another public report.
This is reusable authoring support, not a forced preset or automatic live event.

Compilation reserves the existing eight-character/object capacity, rejects
reused identities and conflicting initial positions, and wraps the exact prior
source so unrelated behavior remains intact. The resulting single source and
test artifact go through normal sandbox staging. Later cast transitions still
use the authority's joint geometry/collision validation and atomic module,
character-history and source transaction. A failed resident record cannot leave
half a gathering published. Individual residents keep their durable identities,
chapter evidence, teams and opt-in services through restart.

The concrete app fixture begins with an empty clearing. A private visit does
nothing; an explicitly shared ruins report brings a guide and challenger into
the actual region-object snapshot. Existing guide chat returns a private route,
and the native challenge dispatcher freezes the trainer's authored team. The
whole cast survives restart and moves to the lookout after the orchard report.
A failure on the second resident's history record rolls back both residents.
The real GM adapter emits one compiled candidate and still refuses when sandbox
publication is rejected. Provider output and sandbox success are fixture
boundaries; no rendered native caravan, paid model invocation, live-world edit
or deployment is claimed. No engine pin, new command or new protocol is added.

### Survey-backed shortcut trails

Two explicitly shared landmark discoveries in the same current revision can
support a physical route improvement. The owner previews it with:

`python -m world.trail_projects camp ruins --label 'Surveyors Causeway' --admin-socket ADMIN_SOCKET`

Add `--apply` to request publication after everyone leaves the generated area.
Preview is read-only and reports the old/new terrain walking distance, new tiles
and actual path. Publication rechecks the exact world, history boundary and map
revision; pending mechanics/battles, immutable-region bindings and normal joint
actor/geometry validation still apply. A preview is not publication approval.
Private visits or discoveries from another revision cannot qualify a project.
There is no automatic construction, reward, currency spend or model invocation.

The compiler adds an ordinary grass walking trail through previously impassable
terrain, using existing native art rather than promising a new bridge sprite.
It preserves every existing walkable tile, the boundary and entry/exit, original
reserved terrain, protected coastal water, and the bounding area around recorded
landmarks/outposts. It refuses mandatory-passage journeys instead of quietly
weakening their topology. A project must shorten the terrain route by at least
four steps and add at most 128 walking cells. Distances describe terrain geometry,
not guaranteed travel time around moving players or residents.

The new exact revision preserves the logical place, ordered authored wildlife
bytes, unchanged resident positions/source behavior, and valid survey evidence.
A replayable construction recipe is archived atomically; old revisions remain
available. No new landmark or current-revision arrival is fabricated. The actual
`trail_opened` public event records endpoints, old/new terrain distance and the
two source discovery records in the same transaction. The player chronicle and
bounded character-history feed expose this committed change, allowing subsequent
agent-authored stories to respond to a real opened route, not a narrative claim.

The concrete authority fixture opens a 100-cell causeway and shortens the
camp-to-ruins terrain route from 249 to 113 steps. Tests cover actual private
visits and explicit sharing, read-only preview, occupied/stale refusal,
publication, every new path cell through authenticated presence, resident
rebinding, survey inheritance, restart, reservation preservation and exact
CAVE17 population retention. Artifact-write and trail-history-write failures
roll back the entire change. This is app/geometry acceptance, not a linked native
rendered session. Plain XL uses existing CAVE16 support; authored-wildlife XL
still needs the separate unpublished CAVE17 native integration. No engine pin,
release integration branch, live world or deployment is changed by this draft.


## Cooperative survey expeditions

Inside a registered generated survey, a guild leader can start
`/guild expedition survey here COUNT`. Every credited member must reach every
clearing on that exact revision after the expedition starts. Entry alone, old
private discoveries and inherited survey progress never count. Members can
spread out and finish at different times. `/guild expedition` shows their own
remaining fieldwork, and new clearing arrivals send private progress hints.
Completing the requested number of full circuits awards the existing 10 guild
XP once and announces the outcome to guild members. It does not change saves,
give items, capture creatures, teleport players or grant battle rewards.

The accepted clearing coordinates are frozen with the goal. Partial circuits
survive restart and pause on other revisions, including changed terrain sharing
the same logical place. Cancel/replacement/disband clears that goal's fieldwork.
These are authenticated, acknowledged client position reports, not independently
simulated travel or anti-cheat proof. Personal `/explore` progress is separate.
Existing chronicle opt-in controls publication: only a completed aggregate
`guild_goal_completed` event with `goal_kind: survey`, place/revision, guild name,
count and XP enters public history. It carries no member names or individual
clearing trails. Existing character chapters can match this outcome to change
resident stories. History-write failure rolls back the final arrival, credit and
award together, allowing the next position report to retry.

The authority fixture covers two members, four clearings each, partial progress
across restart, aggregate publication and character-history consumption, private
defaults, stale/unacknowledged refusal, cancellation, rollback/retry, and an actual
cell-by-cell circuit after restoring the exact old map. Native rendered play is
not demonstrated by this fixture. This uses existing chat and presence transport
and does not change engine pins, live worlds or release integration.


## Independent generated atlases

`python -m world.region_atlas atlas.json --admin-socket ADMIN_SOCKET` previews
an atlas. Add `--apply` to publish it to the existing native destination menu.
The owner supplies a bounded data plan with `title` and 2..8 `regions`, each
containing a distinct `label` and an existing room/link `blueprint`. Labels are
1..20 plain ASCII characters so players can recognize them in the menu. Use
rooms, rounded, organic or maze blueprint styles for distinct layouts. The
compiler validates every map before admitting any. Identical geometry cannot
masquerade as multiple places, and existing labels or pinned places are never
overwritten. Preview checks the world identity and history sequence without
creating archive rows, place identities or public history.

Publication archives all map bytes, the replayable plan, stable place identities,
independent region pins and actual `region_opened` history in one transaction.
A late failure adds nothing. Repeating a successful publication returns the same
manifest after verifying the archived geometry and pins, even after restart.
Players already inside another selected region or the shared default map keep
their exact admission. The new destinations appear through the existing paged
REGION1 menu. Players leave their current generated area before selecting and
entering another, retaining ordinary map checks and same-region multiplayer
visibility. Publication does not activate the shared slot, reset mechanics or
move trainers. No generated-area save behavior is changed.

This atlas format intentionally matches currently supported independent plain
31-by-31 cave destinations. It does not provide seamless borders, overworld
cities, Kanto/Johto/Sinnoh replicas, XL region admission, wildlife or new native
protocols. Those require distinct systems and native integration. The concrete
fixture publishes Tide Vault, Moss Library and Star Observatory while existing
players remain inside, enters different destinations concurrently, changes
regions, restarts and returns through real authority/client protocol dispatch.
This is not a rendered native playthrough or an actual model-provider run.
