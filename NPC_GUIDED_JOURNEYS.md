# Agent-led group journeys

A recurring generated NPC can choose a reachable destination, invite visitors, and actually lead them there. This extends the existing destination pathfinder and walking executor; it does not move players, play a scripted scene, or claim that a character visited somewhere merely because the model described it.

## Player experience

Use `/guild npc nearby` beside a ready recurring NPC. An active offer is marked “guide offered”. `/guild npc guide ID` shows the NPC's invitation and destination, and `/guild npc join-guide ID` voluntarily joins. Up to four people can join the same journey. Follow the actual NPC sprite using ordinary movement. `/guild npc leave-guide` leaves at any time.

The NPC chooses its route from real immutable geometry and walks one collision-checked step at a time. It waits when someone is more than four tiles behind, has a field menu or battle open, or has stale presence. Once at its destination, it waits for the group to come within two tiles. No player is warped or dragged along. A step already admitted may settle before a pause; withdrawal halts its owned pending movement through the existing authority update. Other players and NPCs remain real obstacles.

This is a matched-client generated-map activity, at the existing authority scheduler pace, not a tight native follower formation. Normal Hoenn campaign actors are not relocated. There is no cross-map escort, party partner battle, reward, achievement or inventory effect. Join and offer inspection require being beside the stationary NPC. The current interface uses the existing NPC commands, not a new native menu button.

## Agent composition

The registered `world.guide_players` capability accepts the actor's exact map revision, destination x/y and a bounded public invitation. It verifies the destination using the actual pathfinder before offering. There is no canned cast-specific route or fixed story. Configured agents can select it through the existing general author/plan runtime, alongside observations, dialogue and other supported actions. A live model choosing this tool has not been tested.

The capability remains pending while it waits for voluntary participants and executes real steps. A successful receipt requires committed NPC arrival and the participants' fresh nearby client-reported positions. No visit is inferred from prose. Blocked geometry pauses and retries pathfinding; interrupted movement is not credited as arrival. The 15-minute activity window ends cleanly and permits later independently authored journeys; it is not a lifetime activity budget. Replaced plans retire stale invitations instead of permanently locking an NPC.

The runtime exposes public invitation/destination/status and participant count, not new player identity data. Exact trainer/session bindings are stored privately for restart fencing and removed from the active record on completion. Public history records the NPC's offer and actual outcome without participant names or save identifiers. Restart/disconnect does not silently enlist a new connection with the same name. Every player keeps an independent save and input.

## Verification and ancestry

App-only extension of #368 at 0fb81a35ead39f083a1c95cba40fc6cfe6bbbc56. Native pin is unchanged: #55 babbe0e3272120523d509cecf22705f158429586. Existing published CHARWALK1/CHARREG1 transport renders authority movement; neither pending native upload is included or retried. The inherited app safety mitigation continues refusing the old spectating stream.

The feature stack is not based on released RC12 (app f484577b606348d07337387f14f75ab8cf4970b6, native f7a813317d1b9fec803b48b682f5d74245c79037). Maya's release/integration are unchanged. Full linked/rendered multiplayer QA remains hers.

Tests use actual authority, plan runtime, staged character-action reducer, collision handling and snapshot emission. Coverage includes two actors, multiple consenting players, waiting/catch-up, real arrival, no player coordinate changes, blocked-step cancellation, unreachable destination, restart/session fencing and superseded plans. They do not constitute a live model session or rendered multiplayer playtest.
