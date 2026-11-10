# Mixed campaign adventures

The existing agent capability `world.publish_battle_campaign` now composes ordinary Hoenn visit stages with real existing NPC battle stages. Content remains an immutable, agent-authored branching graph, not a predefined story or a replacement for Emerald's story flags.

A visit node is `{ "visit": { "label": "Destination", "point": [group, number, x, y] }, "next": ["next_node"] }`. Battle nodes retain opponent/win/loss and optional preparation. The existing limits remain: at most 16 nodes, four outgoing choices, an acyclic reachable graph, and 6000-byte document. Ordinary native map bounds are checked; generated aliases are rejected. Static walkability and route feasibility are not established by bounds validation and need playtesting. No teleport, map creation, cross-region transport or scripted canonical relocation is introduced.

## Player journey

Open the existing native campaign board, select a published adventure, travel normally, then choose its Check in entry while standing ready at the exact destination. The ordinary private `/guild campaign check-in` command also works. Inspecting the board alone does not record presence or progress. After check-in, choose a route to another visit or an existing trainer. Battle stages still require the actual normal native challenge and nonce-bound result report. Preparation remains available at battle stages through the prior shop/tutor path.

A shared run uses the same existing host/join/begin interface. Each player checks in voluntarily on their own active save. The group advances only after every member's check-in, then members may advise and the speaker decides the route. Check-ins need not be simultaneous and do not claim a physical group meeting. A party member leaving cancels the run under existing rules. There is no location tracking beyond explicit check-in, no public world-history publication and no shared story flags or rewards.

Visit history is labeled `voluntary_fresh_client_presence`; battle history remains `client_attested`. Neither is anti-cheat verification or proof of a completed fictional narrative. Presence must be current, ready, from the authenticated connection and at the exact authored tile. Busy battles, stale reports, wrong tiles and repeated completion do not advance. Save-lineage binding and SQLite persistence retain progress independently for each player/save across reconnect and restart.

## Candidate and checks

Based on #376 `54843ed10df4c6acbbd2a26a55b189dcadb4a2d1`, using unchanged native #55 `babbe0e3272120523d509cecf22705f158429586`. This is not a rebase onto released RC12 and does not alter Maya's integration. No denied upload or uncertain outdoor-region operation is included. Inherited spectating remains disabled; live direct-provider sessions remain prohibited pending their separate finite-budget correction.

Five new component tests cover the actual CORE campaign-board wire, mixed visit/battle progress, independent shared-party check-ins, advisory choices, invalid presence, save/restart isolation, graph validation and model-plan admission without live providers. Existing campaign tests remain applicable. Linked gameplay, native rendering, real travel feasibility and live-model behavior are still integration QA.
