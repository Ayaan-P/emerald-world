# Shared Safari outings

Characters can publish a finite optional outing using `world.publish_safari_outing` (id, title, group reported-catch target, duration). Players find it with `/guild safari` or `/guild safari ID`. This uses normal Hoenn Safari entry, fees, balls, steps, encounters, captures and exit. It does not change those rules, saves, bags, rewards or story flags.

## Player journey

1. Read `/guild safari ID`. Joining shares group participation/catch/end counts with all world players and agents, including history after leaving. No individual species, party, save identity or trainer name is published, but counts may allow inferences, especially with one participant. The host can access local participant records.
2. Outside Safari, use `/safari ID yes` in the matched native client. This is intercepted locally, never public chat. The authenticated LINK transport negotiates `S JOIN 1 ID` and an opaque `S ADMIT` lease before any gameplay report is sent. `/safari status` must show sharing on before entering. Older servers cannot admit it; no gameplay payload is sent to them.
3. Enter Safari normally. Stock entry/capture/exit callbacks produce cumulative phase/count/remaining-ball/remaining-step reports. Reports never contain individual Pokémon or private party data. Normal captures remain wholly owned and saved by the native game.
4. `/guild safari ID` shows the reported group totals. Each participating trainer/save can contribute one visit, up to four participants. `/safari stop` immediately stops local reporting, without affecting stock play. Completed or stopped participation cannot be replayed/rejoined in that outing.

`world.await_safari_outing` returns only the author's actual public aggregate when its reported target is reached or real expiry occurs. The agent can then choose another existing validated action. No content or response is prescribed; a reported target does not certify captures or produce rewards.

## Transport and durability

This is separate from public chat, CORE story records, spectating and Berry Blender. No `world_bridge.c`, `world_activity.c` or blocked `PLAYER_CLIENT.md` upload is included. It uses the existing authenticated LINK channel without changing native battle command rounds. Safari sharing is unavailable while a native link activity is active. The local sharing state is discarded on transport disconnect; there is no automatic rejoin, cross-save reuse or delayed publication after restart.

The authority binds each lease to its actual link connection, current authenticated presence and save lineage. Reports are monotonic, bounded and idempotent. Duplicate identical snapshots ACK without another event; contradictory duplicates, decreasing counts, increasing resources, reused/foreign leases, expired outings and post-terminal updates fail closed. Coalesced reports are allowed, so a busy frame does not invent missing per-battle events. An exit report may follow the stock warp; intermediate reports require a current Hoenn Safari map. An interrupted visit retains only its already committed counts and is never marked completed by timeout/restart.

These are authenticated **client attestations**, not server-verified battle/capture evidence. Group targets are informational and confer no money, items, Pokémon, progression or NPC training. Native pending delivery is bounded; failure loses reporting continuity, not the user's ordinary Safari game.

## Validation and integration

Component tests cover actual private CHAT discovery and authenticated LINK dispatch, two independent player visits, aggregate-only public history, malformed/contradictory reports, replay, stop, save switching and restart. An actual compiled C reporter test covers opt-in, negotiation, stock callback inputs, cumulative wire output, ACK and shutdown. It does not simulate a capture or certify a linked game build.

App is based on draft #383, not released RC12. The paired native draft is #56 at `739be20ecf1101f84cc2fb272587978350955b6d`, based on published #55 `babbe0e3272120523d509cecf22705f158429586`, not RC12. All denied uploads remain untouched. Maya owns paired linked build, rendered two-client playtesting, integration and release. No live model calls were made.
