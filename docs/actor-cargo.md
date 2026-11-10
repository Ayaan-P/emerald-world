# Transport actual props between linked cave places

Existing `world.take_prop`, `world.navigate_places` / `world.traverse_link`, and `world.place_prop` now compose into transport across supported cave links. No new named scenario or resource type is introduced.

A traversal freezes the carrier, source/destination and exact owned prop identities/versions. Normal mechanic validation still admits the actor movement. In that same database transaction, cargo bindings move to the admitted destination and their custody versions advance. Failure rolls back actor and cargo together. There is no period with the actor in one place and its authoritative cargo in another.

While carried, the prop remains absent from native object snapshots. Placing makes that same ID visible at a valid adjacent destination tile. Custody owns the map binding so old author source cannot duplicate it back in the source region. Collision and normal object validation still apply. Restart preserves both placement and transfer receipts.

Agents discover cargo/version using the existing inventory context and choose their own plans. This enables moving objects between places or bringing existing objects together, not simulated labor, material quantities, Pokemon items, player bags or carrying animations. Actors must remain existing world-owned characters. Original Hoenn/canonical actor movement and uncertain outdoor region admission are unchanged.

Component tests cover real authority take/traverse/place, old-source projection, restart and injected transaction failure. Native rendering and multiple-client QA remain Maya's. Based on app #325 with unchanged native pin and disabled capture experiment.
