# Shared Safari feeder scents (default-off draft)

## The actual Emerald loop

Players make Pokéblocks through the existing game, choose to place one in a real Hoenn Safari feeder, and pay exactly the stock native Pokéblock cost. With `/safari-scents on`, a successfully activated feeder followed by successful native item removal may leave an anonymous public scent for ten minutes. Later opted-in visitors within five tiles can use that flavor profile through Emerald's existing wild-nature selection. Their own stock active feeder result takes priority.

This is a new explicit shared-world rule, not a claim that Emerald already stores shared feeders. The native private feeder still lasts its ordinary 100 steps; the public scent has a separate ten-minute wall-clock lifetime. A later genuine deposit replaces the public scent at that feeder. There is no invented stock count, ownership queue, vote or charge to recipients.

The native nature function has an 80% feeder test, then selects a nature with positive flavor affinity when one exists. Its normal fallback remains. The effect does not change species tables, encounter rate, catch probability, Safari balls, personal step allowance, parties or caught ownership. Balanced/unhelpful flavors may provide no positive affinity. There is no guaranteed nature or catch.

## Player control and feedback

- Development build: `--development --experimental-safari-feeders`; default compile flag `EW_SHARED_SAFARI_FEEDERS=0`.
- `/safari-scents on` enables sharing future real deposits and receiving nearby scents for this connection. No retroactive inventory read/report. Normal feeder selection/confirmation remains stock.
- `/safari-scents status` reports actual nearby flavor values or acknowledged/unconfirmed publication. `/safari-scents off` stops local sharing/receiving; already committed public scents naturally expire.
- A disconnected or rejected report never retries the item action or refunds it. The original private feeder/cost remain; public delivery is best effort, not atomic with a durable personal save.
- Personal feeders can override the public effect using the stock result. Players can also turn the feature off. No partner permission is required.

## Truth, persistence and boundaries

Only the native successful feeder-activation plus item-clear path queues a report. UI cancellation, failed item clear and full feeder storage cannot produce a public deposit from these hooks. The queue waits for the stock conversation to release and revalidates owner, place and bounded age; it sends once. The server validates current authenticated channel, fresh field position, facing and one of 11 hash-verified original Hoenn feeder tiles. Kanto and arbitrary maps are excluded.

SQLite stores the committed scent and an anonymous `safari_feeder_deposit_shared` history event together. Agents can inspect current scents and use this public event with the existing bounded history-reaction executor. No automatic reaction or scripted character arc is installed. History provenance is a consenting native-client report, not cryptographic attestation, proof of disk-save durability, a catch or a Pokémon population. The original item can be restored by ordinary unsaved-game rollback; this design creates no transferable public item or inventory balance.

Receiver replies are query/owner/map/range-bound, expire in at most three seconds (or the shorter remaining scent lifetime), and clear on connection/visit changes. Current personal Safari rules, catch ownership and entry/progression stay private. Snapshot latency exists; this is not exact continuous shared simulation.

## Verification

Twelve synthetic tests pass, including actual native activation/debit callback ordering, actual nature selection and flavor-affinity functions, private-feeder precedence, enabled/disabled core lifecycle under UBSan, SQLite restart/replay/expiry, actual transport dispatch, all 11 native map tiles and the existing history-rule scheduler (with a clearly isolated executor fixture). Tests do not simulate an actual rendered encounter or prove a full native build.

Changed core, Safari and Pokéblock C syntax-check on/off with recovered current headers and host string/ARM shims. Build flag refuses non-development use. Full linking, SDL rendering, input/conversation timing, real save reload and two-client Safari gameplay remain for Maya's integration QA. No real saves or live providers were used. Existing stock feeder range-selection behavior is retained, not redesigned.

App/native ancestry: independent exact #494/#132 candidate, not Maya's branches. No held bridge, Blender, relay or recovery payload is included.
