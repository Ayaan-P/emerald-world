# Original recurring residents in Hoenn

This app-only draft follows #385 at 392eff32dee0d161ccc5f4d15f2699829eec9ac9, retaining native #56 at 739be20ecf1101f84cc2fb272587978350955b6d. Frozen #384/#56, Maya's integration and released RC12 are untouched. This stack remains divergent from RC12. No blocked files or live provider sessions were used.

## What a player can do

Agents discover eligible sites and use `world.populate_native` to create an original, persistent fictional character in an ordinary Hoenn residence. There is no prescribed character, story or goal. Existing normal-map OBJECT/CHARACTER transport makes that resident an interactable NPC; its authored initial team can use the existing optional challenge path, and public nearby speech can produce independent agent replies. Existing NPC generation policy can enroll it using the same configured bounded provider lifecycle as generated-map children. No provider is called by population itself.

Players reach the residence by ordinary campaign movement. Admission or visible resident changes require no players in the room. One resident anchor per room, with no other dynamic objects or mutable terrain there. Current catalog: Oldale House2, Petalburg House2, Rustboro House2/Flat1 1F/Flat2 3F, Slateport House and Pacifidlog House1. Characters remain at their anchor: no normal-map navigation, canonical NPC displacement, fabricated journey, capture or earned experience. Existing stock residents, scripts, door warps, services and saves are not edited.

The world-character count, source/state budget and native object-slot limits remain. Resident anchors are retained, not an unlimited room service. No claim of automatic model-generated residents or native rendered playtesting is made.

## Source-derived safety boundary

`native_resident_sites.py` compiles conservative sites from the exact Expansion asset set. `native_resident_sites.json` records Git blob identities for all 28 inputs, independently checked against native #56's exact tree. The initial source cache had two outdated tileset headers; both were replaced in a separate verification-input directory from the exact published commit before generating this catalog. No shared/native source checkout was overwritten.

Only ordinary Hoenn house/flat interiors qualify. Transition/coordinate/background scripts, connections and non-dialogue commands are excluded. Floors must have native zero collision, elevation 3 and MB_NORMAL behavior. Sites stay two tiles beyond all stock wander extents and exits, have at least three neighboring plain-floor tiles, and preserve connectivity for every conservative combination of original NPC wander positions (bounded at 4096 combinations, otherwise reject). Existing and newly proposed terrain changes invalidate the anchor.

This is a placement catalog, not a native pathfinding mesh or proof of live collision/rendering. The runtime fails closed on a different native PIN; capability discovery reports unavailable rather than disabling unrelated actor inspection. Regenerate/review the catalog before changing that pin. New residents are admitted through the existing isolated mechanic staging and authoritative validators; same-transaction population receipts establish only actual admission.

To regenerate from a full exact native checkout:
`python -m world.native_resident_sites ENGINE_ROOT ENGINE_COMMIT world/native_resident_sites.json`
Then verify recorded blob identities against that exact revision; do not relabel unverified assets as current.

## Checks and remaining QA

Component tests cover two independently authored residents in different normal-map rooms, the actual OBJECT/CHARACTER snapshot and public speech path, persistent ownership/identity across restart, retained source consolidation, optional generated-agent creation recognition, unavailable placement, another player in the room, stock canonical binding names, immutable anchors, terrain rejection and pin mismatch. Source geometry generation is checked against exact engine assets locally. Native rendering, stock scene playthrough, capacity exhaustion in a real client and live author behavior still belong to Maya's paired QA. No full-native build or live provider run is claimed.
