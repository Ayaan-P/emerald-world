# Shared native wild outbreaks (draft)

Agents may use `world.configure_outbreak` with a route from `outbreaks.maps`, an enabled Expansion species name, level 1–100, chance 1–50 and duration 1–60 minutes. Zero minutes closes that actor's outbreak. Another actor cannot overwrite a still-active population. The general capability catalog exposes live populations and expiry; no fixed story or character is installed.

Players travel normally to the route and encounter wild Pokémon in existing grass. `/guild outbreaks` lists public locations, species, levels and remaining time. No menu acceptance, teleport, forced encounter, item grant or party rewrite is performed. The configured percentage is the native outbreak roll after normal encounter checks, not a guaranteed encounter on each step. Sweet Scent uses the existing land-outbreak path. Water, fishing, scripted encounters and generated maps are unchanged.

## Real native effects and save boundary

`OUTBREAK1` clients receive `WILD_OUTBREAK group num species level chance seconds` only for their currently reported route. The normal snapshot transaction admits this row atomically. It expires locally with the snapshot lease, clears on a row-free snapshot, and is unavailable after disconnect/map change. Old clients get no new row; new clients retry older servers without the suffix on the existing AUTH fallback.

The native adapter feeds the existing `DoMassOutbreakEncounterTest` / `SetUpMassOutbreakEncounter` pathway. It invokes actual `RandomPercentage`, Repel check and `CreateWildMon`. Native generation supplies the individual's personality, IVs, ability and level-up moves. Ordinary encounters, catches and their normal player-save effects are still owned by the game. This is not an autonomous NPC capture, migration simulation, observed sighting, or guaranteed spawn.

A trainer's active saved outbreak **on that map takes priority**. Its species, special moves and duration remain untouched. No shared outbreak data is written to SaveBlock1; expiry uses durable authority UTC deadlines and survives restarts without renewing duration. At most one row per reviewed route is retained.

## Source scope

Reviewed `land_mons` entries in Expansion `src/data/wild_encounters.json` at `2abe34bd2b39ec9085e1d1aa5eda4cd5e65b8ed6`: Routes 101–104, 110–121, and 123. Route 130 / Mirage Island is intentionally excluded due to conditional land availability. Not every route in these numeric ranges has a new map; the exact catalog has 17 names. Native map/terrain checks still decide whether an encounter is possible.

## Validation / integration

Paired component tests execute the real authority capability plan and snapshot through C extracted from the actual native parser/getter/outbreak functions. Tests replace RNG and Pokémon construction with deterministic function stubs to inspect calls; they do not prove rendered battles or capture/save/reload. They cover private saved-outbreak precedence, Repel rejection, stale/disconnected leases, map changes, expiry/restart, legacy-client suppression and invalid species/ranges.

This branch builds on the #348 campaign candidate, paired native #44, **not released RC12**. RC12 is app `f484577b606348d07337387f14f75ab8cf4970b6` and engine `f7a813317d1b9fec803b48b682f5d74245c79037`. Maya must reconcile release fixes and do linked/native, two-client, actual encounter/capture/save QA. No release or integration branch is modified.
