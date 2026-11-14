# Native-trait habitat composition

Agents can inspect enabled Pokémon traits and create actual playable habitats without manually spelling twelve encounter slots. This is content authoring, not simulated ecology, autonomous catching, training or evolution.

## Tools

`world.inspect_species(criteria, page)` exposes twelve matching records per page. Criteria is compact JSON with types (one to four native type names), generations (distinct 1..9), bst ([minimum, maximum], 150..720), levels ([minimum, maximum], 1..100) and unsigned seed. Types use OR matching. Results include native species ID/name, types, introduction generation (from National Dex order, not family-header generation), base-stat total and catch rate. The complete catalogue is not injected into every model prompt.

`world.compose_habitat(label, blueprint, profile, rate, criteria)` selects twelve distinct matching species using a reproducible seed, orders them by base-stat total and grades levels across the requested range. Existing native land encounter slots make later entries rarer under the normal slot distribution; native Lure effects may reverse slot selection. It compiles the existing format-10 wildlife payload and opens a separate immutable 31x31 region. It never replaces the active shared map. The actual chosen slots are retained in the successful authority receipt.

Agents choose the layout, types, generations, strength range, levels, rate and cave visual profile. No named biome/scenario is mandatory. Base stats and type are useful authoring constraints, not proof a species naturally inhabits a location. The compiler does not infer appropriate evolution levels. The existing explicit-slot habitat tool remains available for intentionally different populations.

## Source and constraints

`world/encounter_traits.json` contains 945 supported base-species entries extracted from native #49, with engine commit and all 28 native definition/configuration input SHA-256 hashes. Source family/configuration/identity files were checked against that exact remote commit. `scripts/export_encounter_traits.py` preprocesses enabled family definitions and evaluates numeric stat expressions using C. It omits forms and entries whose metadata cannot be resolved by the bounded extractor rather than guessing. The live enabled-species catalogue is intersected again before composition.

Legendary, mythical, Ultra Beast and Paradox entries are excluded using native flags. Fewer than twelve matching species is a clear refusal, not duplication or fallback to unrelated types. A changed candidate native pin requires regenerating/reviewing traits. Existing map/state/archive capacity and plan bounds remain. Profile and rate validation still belong to the original wildlife compiler.

## Player journey and verification

The host runs the existing configured author. An agent can inspect matching species, compose a habitat, populate it, and connect it through the existing world capabilities. A compatible region-enabled CAVE10/REGION1 client selects the new destination and enters normally. Its native wild encounter machinery consumes the selected species/levels. Physical cave connections use the separately implemented passage tool. No player save, party or bag is rewritten by this capability.

Tests run actual authority admission, archive publication, wire transfer/ACK, native-format decoding, restart, query/seed variation, a second actor and rollback. They do not claim a rendered encounter, catch, full linked build or live provider run.

This is stacked on #356 and retains native #49. It is not based on released RC12. No outdoor REGION1 admission or uncertain geography operation is reused. Maya owns integration, linked/rendered multiplayer QA and release.
