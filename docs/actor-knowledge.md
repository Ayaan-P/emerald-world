# Factual character-to-character knowledge exchange

Two generic tools extend the existing capability runtime, without a named scenario:

- `world.share_observation(target, expected_version, observation)` passes the sender's actual successful `world.observe` receipt to an adjacent world character. Both must be idle and in the exact same generated place/revision. It verifies the immutable authority event, not arbitrary text or a result-shaped object. Duplicate delivery is idempotent.
- `world.recall_report(delivery)` returns only a report actually received by that actor, including sender, original observation, dated snapshot and `report_revision`, `report_x`, `report_y` for normal scalar result references.

The existing configured character author observes a delivery event and independently chooses a next plan. Nothing makes it agree, obey, or automatically travel. Discovery exposes the most recent 32 received report identifiers per actor; older reports remain durably addressable. Reports are immutable historical information, not proof of current entity positions. They cannot masquerade as a fresh first-hand `world.observe` receipt for terrain/object actions.

A complete composable path is: observe → approach recipient → share own observation → independent recipient author turn → recall → navigate using report coordinates → observe again. Local authority tests run this path through real movement staging and restart. They use authored test plans, not a live model or rendered scene. This adds no canonical Hoenn movement, player data, forced player interaction or capture activation. The optional capture experiment inherited from the parent branch remains disabled.

No new native dependency: paired pin remains 570a0c3547de7eeb64b8d5373e959370fb486984. Based on app #324, separate from Maya's RC integration. Maya owns linked multiplayer/model QA and release.
