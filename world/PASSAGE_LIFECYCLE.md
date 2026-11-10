# Revision-bound paired passage lifecycle

Independent app branch on #421 (`7967ed34a8696a398c09fd2e89dc596de1066673`).
Native remains #79 (`d1075e135c443e4e2cf1940fffa9657c3ed371ec`), unchanged.
Not Maya's #410/#72 or released RC12.

## Actual behavior

`world.set_passage(connection, revision, operation)` closes or reopens BOTH
physical ends of an installed paired cave connection. Discover IDs, exact current
revision, owner candidates and travel blockers under `passage_lifecycle`.
Operations are `close` or `open`; there is no endpoint redirection or destruction.

Ownership is inferred only from successful authority creation receipts or the
persisted original region-network author. Missing or ambiguous ownership fails
closed. Hand-installed one-way links cannot be claimed by this capability.
The exact installed source/destination records and actual endpoint props must
still agree with the original connection definition.

A closure is functional, not cosmetic:
- Native REGION_PROP snapshots display **Passage closed** at both ends.
- Interacting with either endpoint refuses a transfer and explains closure.
- NPC observations no longer offer traversal and route discovery excludes both
  edges. No player/NPC is moved merely because route availability changed.
- Reopening preserves the original destination, object identity and placement.
  Its new revision invalidates prior NPC link observations and stored routes.
- Native transfer consent and ACK validate the bound passage revision. The
  original CAVELINK1/CAVELINKW1 transaction, return warp and recovery are reused.

The operation refuses to run during mechanic admission, any affected player
transfer (including consent, download and committed-but-not-arrived phases), or
an active NPC linked journey still depending on an endpoint. Finish the journey
or explicitly cancel it first. Canceled/outdated plans are not fabricated into
arrivals. No forced cancellation, teleport, reroute or loss of a return path.

This controls passages, not ownership/access to entire places. Existing region
selection menus and the player's original Hoenn return remain available. Places,
geometry, populations, battle progress and archives are not deleted or rewritten.

## Durability and authority

Both directions consult one durable connection record. Availability changes and
public receipts are committed in the existing actor-runtime DB transaction; a
failed result receipt rolls back the route change. Restart retains closure and
revision. Original cave_links rows and historical receipts remain intact.

Availability is authority-owned SQLite state, not a field that an authored
mechanic can set to manufacture ownership. If the underlying connection definition
changes, the controlled passage fails closed rather than silently pointing to a
new destination. No new native wire operation, save field or held file is needed.

## Tests and limitations

46 selected component tests: 44 passed, two existing sandbox/provider skips.
Tests cover an actual authored connection, both-direction closure, native caption
frames, transfer rejection, exact-revision reopen and the consent/ACK/arrival
sequence after reopening; blockers at each in-flight phase; private source return
preservation on abort; persistent closure after restart; pending NPC-route
fixtures; and actual actor-plan receipt rollback.

The native decoder/pump component test uses the existing habitat-link fixture.
The default older plain-cave fixture refuses wildlife format 10 and fails the
same test on the unchanged parent branch; select the matching fixture with
`EW_LINK_NATIVE_SOURCE=/path/to/native-habitat-links`. This is not a linked build
or rendered playtest of the currently pinned native head. Full current-native,
rendered two-client, suspend/reconnect and NPC-journey QA remain outstanding.
No live provider calls were made. No denied or uncertain operation was retried.
