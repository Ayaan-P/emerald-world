# Optional spatial co-op signals

Players can use `/signal on`, then `/signal look`, `/signal meet`, `/signal help` or `/signal danger` in ordinary public Hoenn towns/routes. `/signal off` clears and disables markers; disconnect resets opt-in. Sending publishes the authenticated trainer identifier, current reported tile and intent to opted-in nearby players on that map. These are client-reported intentions, not verified danger, arrival or assistance.

The server retains an eligible signal for eight seconds, enforces a two-second sender cooldown and selects one latest signal within six Manhattan tiles. Native rendering uses the stock field-arrow sprite without a collision object or save modification. Sprite exhaustion skips rendering. Kind/name appear in chat; arrow animations are directional stock graphics, not custom semantic icons. Native expiry is bounded by frame pumps, not an exact wall-clock guarantee during pauses/network delay.

World-owned, stationary native-map residents can invoke discovered `world.signal(kind)` from their actual position. This does not give agents automatic access to human signals. Original actors, generated places, interiors, Secret Bases, facilities and underwater maps are excluded. No teleport, rewards, inventory change, canonical script override or guaranteed recipient acknowledgement.

## Ancestry and verification

Separate draft based on app #403 (3d8875cc71930362f8a478545cfd06f2ccb511d2) and native #65 (722ce4b323a8713d9a16d0cbf21b45e5b1e1acf4). This stack is not rebased onto RC12; Maya's frozen #384/#56 and integration are untouched.

72 selected app tests: 70 pass, two existing provider sandbox skips. Two compiled native component tests cover protocol opt-in/expiry/bounds and the actual renderer with engine stubs, including exhausted/recycled sprite slots. Full linked build, rendered camera/palette behavior and two-client play remain for integration QA. No live provider calls.
