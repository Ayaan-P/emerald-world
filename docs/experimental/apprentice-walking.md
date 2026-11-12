# Transient apprentice walking (default-off follow-up)

Builds on native #144 / app #508. This is a local walking representation of the existing RAM-only apprentice outing, not a network-replicated world NPC or a new persistent Pokemon owner.

## Player experience
Start the outing in the original Battle Tower lobby with `/apprentice start`. With the additional experimental walking option enabled, the apprentice's actual native trainer-class sprite appears on a clear, genuinely vacated on-foot tile. It follows a bounded trail of observed adjacent footsteps using native held-movement animation and native collision checks. The original wild-battle companion remains available independently of sprite availability.

A lets the player talk to the transient character through a real native script. The character remains visible but does not compete with active dialogue/scripts. Ordinary NPCs, players and peers can pass it; it yields rather than blocking a corridor. It never pushes another object, changes a terrain collision or asks others to vote.

This first walking slice is deliberately on-foot only. It disappears/rejoins around warps, bikes, surf, large displacement, crowded/blocked terrain or object-slot exhaustion. It does not reproduce an entire continuous cross-map walk or teleport an active sprite through a wall. After a map change it waits for a new actual footstep, rather than inventing an arrival path. When no object slot is available, it waits without evicting a native character. `/apprentice end`, disconnect and invalidated saved mentorship dismiss it. Battles keep #144's real private-party outcomes.

## Save and engine boundaries
- No `FNPC_ENABLE_NPC_FOLLOWERS` change, NPCfollower SaveBlock3 field, save schema, story flag or saved script pointer.
- The transient template lives in RAM. Its local ID 159 is outside current bridge ranges; both active objects and current saved native templates are checked before admission.
- Ownership checks bind object-array slot, active state, local ID, map, graphics and marker. A recycled/replaced slot is not removed or rewritten.
- The actual native SaveObjectEvents copies a zero object only for that exact owned transient slot. Other saved objects follow the stock path. LoadObjectEvents and ResetObjectEvents forget transient ownership.
- The common field cleanup removes the owned object before field sprites change owners for battle/transition. Frame updates never destroy an old field sprite during battle/menu callbacks.
- Terrain/elevation/warp tiles and dynamic occupied tiles are conservatively checked. Movement follows only actual adjacent observations, bounded to eight queued tiles. Overflow or discontinuity abandons the visual trail safely.
- Script/template lookup recognizes only the currently owned object. The interaction script does not replace the original Tower mentoring scene or set story flags.
- Human co-op and normal stock followers retain their original priorities; the sprite does not enroll anyone or report their identity.

## Validation
Six synthetic tests pass. The enabled/disabled walking C harness, under UBSan, invokes the actual walking module, actual SaveObjectEvents/LoadObjectEvents, actual native object collision loop and actual apprentice graphics lookup. It exercises ordinary walking, native move requests, visible script pause, pass-through for players, companion collision with another object, exact save exclusion, unrelated object preservation, load cleanup, slot failure/retry, reserved-ID collision, changed-map/rejoin, bike/outing dismissal, prebattle cleanup, water/collision/warp exclusions, nonadjacent displacement, and recycled slot ownership rejection. The #144 actual entry/return/AI/difficulty suite also still passes.

Graphics tables, sprite allocation/animation, terrain queries and other engine services are synthetic fixtures. This is not a rendered movement test or full native build. Header-based syntax passes for both companion modules with walking on/off using recovered native headers. No full exact native link, real sprite palette/timing, doors/stairs/crowded-map playthrough, network-peer visual acceptance or real-save QA is claimed. No real saves were used.

`EW_APPRENTICE_WALKING=0` by default. `--experimental-apprentice-walking` requires `--development --experimental-apprentice-outings`. Keep both experiments disabled until Maya integrates and performs native gameplay QA.
