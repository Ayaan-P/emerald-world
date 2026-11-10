# Constraint-based connected regions (draft)

`world.generate_region_network` lets an enrolled world author choose topology and layout constraints rather than supply every room rectangle and passage. It is available to original-cast and generated-character plans. The agent supplies a literal label prefix and a bounded JSON `constraints` string:

- `places`: 2–4 distinct generated places.
- `rooms`: 2–4 rooms per place.
- `loops`: 0–1 independent cycle in the region graph.
- `branching`: maximum region graph degree, 1–3.
- `style`: rooms, rounded, organic or maze.
- `seed`: unsigned 32-bit integer.
- `corridor_width`: 1–3 tiles.

A deterministic binary partition packs room rectangles into each 31×31 interior. Seeded connected graph selection supplies room corridors and region passages, respecting the requested branching/cycle constraints. The established blueprint compiler produces and validates the actual native cave bytes. Identical arguments reproduce identical geometry; impossible constraints fail rather than silently change the requested topology.

The result goes through the existing region-network publication transaction. Admission installs real persistent selectable places and bidirectional passage props. Players with matching REGION1, prop and CAVELINK1 support select an entry place, enter using the existing cave entrance, and choose its passage interactions to reach neighboring places. The native transfer handshake and return-warp behavior are unchanged. Agents can subsequently populate, observe or navigate these actual identities using existing capabilities.

This creates supported plain caves, not outdoor regions, new artwork, a story, simulated exploration or encounter populations. It does not replace the shared destination or original Hoenn maps. The existing 850-character compiled-network budget remains: some combinations, especially four places with four rooms and longer labels, require fewer rooms or shorter labels. Existing world region/object/source capacities remain unchanged.

A staged request is not completion. If admission fails after opening the archive entries, those exact places remain available; reissuing identical arguments resumes the same network without duplicate places. Only the existing successful poll receipt claims installed connections. A new seed deliberately produces a different proposal, not an update to the old network.

Validation uses multiple seeds and styles, actual authority admission, native-shaped passage/ACK/arrival round-trip through in-memory client fixtures, distinct actor generation, failed-admission recovery, restart and unchanged shared-world checks. No live model, rendered game, full linked-native QA or seamless-overworld claim.

Based on #373 at d7f7ab97b4619cbdc21aa6540810df024066dd93, unchanged native pin babbe0e3272120523d509cecf22705f158429586. This is the divergent feature stack, not RC12 or Maya's integration. All three pending denied uploads are excluded. Direct-provider co-player sessions must not be run while their separate finite-budget publication is pending.
