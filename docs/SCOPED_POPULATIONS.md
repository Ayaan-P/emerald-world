# Populated destinations with scope-aware native snapshots

The authority can now retain more than eight world objects without sending more
than eight to a native client. Object capacity is enforced per exact map and
immutable generated revision. Only the player's current scope appears in the
OBJECT / REGION_OBJECT / REGION_PROP part of each replacement snapshot.

## Real player and author flow

Existing `world.create_place`, `world.create_habitat`, `world.populate` and cave
links remain the authoring/travel tools. Agents need not replace the inhabitants
of one destination to populate another. Two players in different opened caves
can each see and interact with their own eight NPCs/props, even though those caves
use the same native map number. Returning after a server restart restores the
same persistent identities. Standard-map dynamic objects are likewise scoped to
the player's current map. No new protocol or larger native sprite array is used.

Population admission, unique object/individual identities, exact archived
geometry, collision, character version transitions and native battle ownership
remain unchanged. A ninth object in one scope fails admission atomically; it is
not silently omitted or prioritized. This is real shared authority population,
not separate duplicate NPC instances for each player.

## Deliberate limits

This is bounded multi-place population, not an unlimited world:

- At most 64 total current objects, eight per map/revision.
- At most 32 persistent world-character records, including away/retired records.
- Existing 32 KiB admitted mechanic-state, source/output and sandbox limits remain
  unchanged. Rich records/plans can exhaust that budget before the count limit.
- Existing population-source consolidation limits remain. This does not remove
  the 16 population receipts per unconsolidated source or invent a safe automatic
  consolidation procedure.
- Existing configured author-following limits and recurring per-character cost
  controls are unchanged. A larger visible population does not silently enroll
  more model-driven actors or spend more API budget.

No original cast is duplicated, no original map geometry or player save is
changed, and no new outdoor-region admission is introduced. This work does not
retry or reconstruct the earlier uncertain outdoor-v16 operation.

## Complete, bounded author inspection

Expanded worlds can exceed a single 64 KiB host inspection line. Updated host and
GM helpers request an optional chunked response. The authority freezes one full
inspection on that private admin connection, serves sequential bounded chunks,
and verifies order, expiry, total size and digest. Each line/queue item retains
the existing limit; total inspection is bounded to 256 KiB. No state or NPC is
silently truncated. A legacy host client gets a clear upgrade/refusal message if
its inspection is too large. Updated helpers still accept ordinary old-server
responses.

This is not a new player endpoint, a broader public snapshot or a change to the
mechanic sandbox. The frozen transfer expires after 30 seconds and is discarded
on completion, a replacement transfer or connection closure. Request/reply
helpers retain their timeout and GM request-size limits.

## Verification and integration

Production-authority component tests commit sixteen NPCs across two actual
opened revisions, authenticate separate visitors, verify eight scoped wire rows
each, restart and revisit. A real `world.populate` plan admits the fifteenth NPC
in another region and delivers it in that region's native snapshot. Tests cover
same-scope overflow rollback, ordinary-map filtering, complete large host/GM
inspection, corruption/order/expiry, and legacy refusal.

Socket-dependent GM integration tests cannot run in this executor because
creating an AF_UNIX socket raises PermissionError. No bypass was attempted.
In-memory wire tests exercise production handlers but are not rendered gameplay,
a linked native build, real socket integration or live-model validation.

App-only atop #354; native #49 remains
be08691d7e5b9d3cb19fdfed0e742849180d8297. The stack diverges from released RC12:
app f484577b606348d07337387f14f75ab8cf4970b6 and native
f7a813317d1b9fec803b48b682f5d74245c79037 must be preserved during Maya's
integration. Maya owns integration, multiplayer/rendered QA and release.
