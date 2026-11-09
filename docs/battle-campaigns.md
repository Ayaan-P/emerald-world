# Optional branching battle campaigns

This is a short Pokémon battle campaign foundation, not a tactical-grid engine,
party draft, permanent death mode, synchronized multiplayer battle or story rewrite.
An agent uses `world.publish_battle_campaign` to register an immutable graph over
existing world NPCs. There are no built-in named scenarios or invented opponents.
The configured author receives the capability and public campaign catalog; no live
model call was made during development. The usual 1024-byte plan-step bound applies.

Players use `/guild campaign list`, `start ID`, `status`, `choose NODE`, and `leave`.
They walk to the current opponent and select the existing native Battle option.
A win or loss offers the corresponding authored routes; the player chooses which
route to pursue. Empty routes end the campaign. Cancelled/aborted/other outcomes do
not advance it. Status supplies current object coordinates and exact generated
revision where applicable. Absent opponents wait; the system never teleports,
forces a battle, disables normal fights, or freezes autonomous NPCs.

The JSON has `id`, `title`, `entry`, `nodes`. Each node has an existing `opponent`
character ID and `win`/`loss` lists of next node IDs. Up to sixteen reachable nodes,
four choices per outcome, no cycles. A new graph requires a new ID. Actual teams
are selected by the existing challenge adapter at battle admission, not copied or
invented by campaign registration. Persistent companion/full-state handling and
all original native battle checks remain intact.

Progress is private to authenticated trainer AND synchronized campaign save lineage.
The existing CORE1 MILE safe-idle snapshot must establish that lineage first; no
chronicle sharing switch is required. Other saves and trainers are independent.
Restart retains routes and reported results. Disconnect during an unreported battle
leaves that node available, not victorious. A lineage change during a pending fight
cannot credit either save. Normal battles outside the enrolled current node have
no effect. The exact pending nonce/version/identity is consumed once by the existing
adapter, with campaign progress and private report committed in one transaction.
Results are client attestations, not server-simulated or anti-cheat-verified victories.
No campaign rewards, public history, agent knowledge of private progress, companion
training, bag changes or changes to original story flags result. Native battles keep
their existing ordinary effects. Each trainer chooses routes independently; no
shared-host narrative ownership or forced group consensus.

## Integration and tests

Independent child of app #339 (86104d3f); unchanged native #40
8e409094ccd226a66c9cf8bfef2f545f2be52c28. This is NOT based on released RC12
app f484577b / native f7a81331. Maya must reconcile release fixes and perform linked
native, UI, two-client and save/reconnect QA before integrating. No merge/release.
Fixtures drive actual authenticated challenge/result dispatch and private guild
commands, but do not run rendered battles or a live provider.
