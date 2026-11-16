# Persistent native Cut grass experiment

Default off (`EW_PERSISTENT_CUT=0`). Build with `--development --experimental-persistent-cut`, then explicitly opt in for this connection with `/shared-grass on`. `/shared-grass off` stops future reports; a report already sent may still commit. Reconnecting disables the opt-in.

## Actual player loop

In an existing archived, shared format-9 63×63 generated outdoor place, select an owned Pokémon that actually knows Cut and use the ordinary native field action. All original eligibility and animation remain. No additional PP, item, money, reward or participation requirement is imposed.

The completed action submits only the exact tall-grass cells that the native engine changed to ordinary grass. The authority commits those cells through the existing walkable terrain transaction. Other compatible visitors receive the normal terrain broadcast; later visitors load the persisted surface. This changes actual metatiles, including the stock grass encounter surface, not merely a label, prop or journal. It can make a repeatedly used path comfortable while leaving surrounding grass available for encounters. No one must approve another trainer's routine choice.

A wrapped, nonmodal 20-second message reports sending, committed/syncing, rejected or unconfirmed. `/shared-grass` recalls status. It does not take control from the player or open a voting screen. Shared changes remain until a subsequent legitimate terrain edit, rather than regrowing automatically or inventing a scarcity economy.

The existing durable `terrain_changed` history contains actual changed cells. Existing world-history/terrain tooling can inspect and respond to them, but this implementation does not invent an NPC's reaction, authorship, achievement or off-screen activity. Agents remain free to decide subsequent responses through existing mechanisms.

## Exact boundaries

- Only existing archived shared format-9 outdoor places. No original Hoenn-route persistence, XL worlds, region instances, trees, long grass, ash grass, water, new passages or collision-changing terrain.
- Stock Cut remains unchanged when the experiment or local opt-in is off. Ability-only substitutes without a learned Cut do not submit shared changes.
- Map identity hashes the original event/cast/template bytes. The terrain snapshot hash is separate and compared under the same authority lock as commit.
- Authenticated current link/presence, fresh exact map/position, matching cave admission, no transfer, bounded distinct cells within the native maximum radius, current tall grass, native terrain validation, endpoints/NPCs, queue capacity and existing overlay limits all apply. Existing overlay storage is bounded to 512 edited cells; exhaustion rejects rather than inventing a resource cost or overwriting cells.
- The authority validates the request and real terrain commit, but the native action report is not cryptographically attested gameplay. No partner identity, private party, move list, item ownership or save progression is sent or copied.
- Repeated/stale reports cannot replay an old clear over a later edit: the exact snapshot must still match. Rejection or uncertain delivery restores the CURRENT cached authoritative surface, not the captured old tiles. A lost reply does not prove server rollback; reconnect/normal snapshot transfer resolves it. No automatic retry.
- Terrain and response travel on existing separate channels. COMMITTED means durable authority state, not proof every client has rendered it. Native restoration is identity/save guarded; a later normal terrain broadcast is authoritative.
- No personal save layout changes, no Pokémon/PP changes beyond ordinary Cut, no autonomous provider calls. No modifications to held world_bridge.c, Blender changes, Maya's branches or release deployment.

## Verification and remaining QA

Eight synthetic tests exercise the actual authenticated server dispatch and actual existing terrain transaction, persistence/broadcast, SQLite interruption rollback, stale/replayed reports, invalid contexts/cells, incompatible inside peers/queue exhaustion, native completion/disconnect/timeout with experiment on/off, exact canonical identity/terrain hashes against Python SHA-256, and restoration from current rather than obsolete tiles. Actual modified Cut C source syntax-checks with on/off definitions against recovered native headers; generated_map.c syntax-checks with the full terrain/XL cohort. Existing pointer-size/deprecated-party warnings remain.

These are source/component tests, NOT a full native link or rendered playtest. Required before enabling: exact native build; two clients cutting/receiving the same place; normal and Hyper Cutter animation; snapshot edits during animation; lost ACK versus terrain ordering; disconnect/re-entry; later visitor and server restart; native encounter behavior before/after; chat layout/controls; ordinary Hoenn Cut with feature disabled. No real saves were opened or written.

Ancestry: independent follow-on to app #493 / native #131. Maya owns integration and release. No claim of a finished original-route living world, autonomous ecology, shared wild individuals or completed linked QA.
