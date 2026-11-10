# Player-built exploration charts

Separate child of app #396 (be7e59142e48ae5e9f212e6b783bb09180f0f104), with
its unchanged native #58 pin. Not based on released RC12; frozen #384/#56 untouched.
No new native protocol, borrowed assets, player save writes or live model calls.

In an acknowledged generated place, open normal in-game chat:

- `/guild chart private`: retain tiles this save actually reports standing on.
- `/guild chart share`: read disclosure; no change yet.
- `/guild chart share yes`: publish future visited tile coordinates to the shared
  world chart. It never backfills your older private path.
- `/guild chart stop`: stop recording and sharing. Existing tiles remain.
- `/guild chart show`: 9x9 text minimap around you; `@` is you, `.` visited,
  `?` uncharted. Add `shared` to inspect the community's reported tiles.
- `/guild chart show shared X Y`: pan to a specific tile on this place's chart.
- `/guild chart route shared X Y`: cardinal directions through connected reported
  tiles. This is remembered navigation advice, never movement or a safe-path guarantee.

This adds cooperative mapping rather than a full-map reveal: players can map separate
corridors and use each other's disclosed discoveries. Only sampled occupied tiles are
recorded, never an inferred straight line between reports, nearby unseen terrain,
objects, encounters or private conversations. State is authenticated client-reported
presence, not independent proof of travel. Dynamic obstacles may invalidate a route.

Recording/sharing is off by default, scoped to the connection and current save lineage.
Switching saves stops it; reconnect/restart does not silently renew consent. Private
charts remain trainer/save-scoped; shared rows contain only exact map revision and
coordinates. Other players can infer routes from those coordinates, which are public
and persistent. The trusted host retains private charts. No chart enters public world
history or character-provider prompts automatically. This is an in-game chat map,
not a graphical HUD, original-Hoenn map, NPC perception or exploration achievement.

Exact revision keys prevent reusing paths across changed layouts. Plain and other
currently acknowledged generated formats use the existing connection/geometry decoder;
this adds no outdoor-region admission or cross-map transport. Charts survive database
restart without automatically reopening participation. No fixed lifetime visit cap.

Verification: 18 focused tests pass, including two-player contribution/route use,
private versus shared scope, save and revision isolation, restart, stale presence,
chat command integration and existing cargo/guild history regressions. These use
real authority fixtures and generated geometry; no rendered native session was run.
The separate legacy private-command suite has 12 fixture errors (missing shared_cave
or cast_scenes); the same 12 errors reproduce on unchanged parent #396. This change
does not claim that suite passes or modify its fixtures to hide the failures.
