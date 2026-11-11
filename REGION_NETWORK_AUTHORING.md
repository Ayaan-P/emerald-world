# Agent-authored connected region networks

`world.create_region_network` publishes a bounded connected graph of actual
persistent 31x31 plain cave destinations through the existing region admission,
geometry compiler and native physical-passage system. It is not a named story,
preset dungeon, outdoor-region implementation or simulated journey.

The `network` argument is compact JSON with `places` and `links`. Each of 2–4
places supplies a literal menu label and an existing cave blueprint (rooms,
internal links, entrance_room, exit_room, optional style/seed/corridor_width).
Network links are distinct undirected place-index pairs, at most four, and must
connect every place. Exact duplicate geometry is rejected rather than inventing
a second identity. Agents choose layout, labels and graph; no specific actor or
narrative is required. Existing create/populate/observe/navigation tools remain.

## Actual player experience

Compatible players choose an opened destination through the existing REGION1
menu and cave entrance. Admitted native REGION_PROP passage objects identify
neighboring places. The ordinary A-button link confirmation and transfer carries
them through that graph using CAVELINK1, preserving the existing Hoenn return
warp mechanism. A network can branch or loop. NPC population and habitat authoring
remain separate existing capabilities; this operation creates plain caves only.
No new graphics, seamless streaming, player visit or construction labor is claimed.

## Atomic boundaries and recovery

All blueprints, distinct identities, graph connectivity, capacity and jointly safe
passage placements are validated in the initial executor transaction. A validation
failure rolls back new archives, identities and openings. The existing limits
remain: 32 opened regions and the current per-place/global object budgets.

A successful initial request commits real opened places and a pending actor
receipt, then stages one mechanic source for all passage props. Those places may
therefore be selectable before their passages are admitted. This is explicitly
not a completed connected network. The author context exposes the request and
admission status; generic pending/blocked receipts remain available.

After admission, all exact link rows and the final success receipt commit in one
transaction. Failure cannot leave half-installed link rows. Reissuing the exact
same actor/network document resumes retained destinations and admitted props;
it does not mint replacement identities. Independently changed props refuse link
installation. This is not an automatic retry after an operator denial.

## Pairing and verification

Based on #364 301f79e7724753ea55388ea4f29080a56077c451, with unchanged native
#53 879b6344aeeb3c4e65d0feb00f98655299225635. The single-pair connection tool now
shares its existing safe placement helper with network authoring; its behavior
and tests are retained. The source-generation path still uses normal staged
mechanic admission, not direct bypass of the sandbox or object validator.

Tests use actual authority/compiler/executor, archive/identity records, source
admission fixtures and native-protocol reference client. They traverse three
places through two successive real transfer handshakes and check restart; another
actor creates four branching places. Invalid graph/placement, interrupted source
admission and receipt-failure recovery are covered. Admission uses deterministic
in-process fixtures, not a claim of sandbox or rendered native validation.

No live model call, linked game or rendered multi-client playtest is claimed.
Maya owns integration and final QA. This stack is not based on released RC12
app f484577b606348d07337387f14f75ab8cf4970b6 / engine
f7a813317d1b9fec803b48b682f5d74245c79037; her release/integration are untouched.
The uncertain earlier outdoor v16 REGION1 operation was not retried or recreated.
