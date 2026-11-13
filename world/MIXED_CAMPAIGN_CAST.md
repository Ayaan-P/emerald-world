# Mixed human/NPC campaign roles (draft)

Shared split stages can now assign generated-map visit roles to independently
consenting world characters. Battle and ordinary-Hoenn visit roles still need
human trainers. No NPC battle, capture, level gain or canonical travel is
simulated.

## Connected player journey

An author publishes a normal campaign graph. A generated destination uses
`visit: {label, point: [group, num, x, y], revision: <exact immutable hash>}`.
The authority checks archived geometry, matching native alias, walkability and
transit endpoints. Existing ordinary-map visit documents are unchanged.

A player hosts through the existing native campaign board and begins a split
stage. It may have fewer humans than roles only when every spare role can be a
generated visit. At least one human is required. Every human keeps their own
save-lineage-bound progress and must select a role.

The speaker selects “Publish invite NPC for ROLE” on that board (or uses
`/guild campaign invite-npc ACTOR ROLE`). The board explains that this publishes
only the requested destination. It publishes no party identity, private run
key, participant list, human result or private history.

An enrolled character sees its invitation in capability discovery and receives
a relevant event. Its configured author may choose `world.decide_campaign_role`
with accept or decline. Acceptance does not move it. The actor then chooses
its own `world.navigate` plan and uses the returned arrival receipt in
`world.complete_campaign_role`. This is general capability composition, not a
forced plan or scripted personality. No provider response is guaranteed.

The actual movement executor must commit a post-acceptance journey to the exact
destination, and the NPC must still be there and stationary when reporting.
The party waits for all human reports and NPC arrivals before opening the next
route. The speaker chooses with advisory input as before. Human check-ins remain
client-attested, while NPC arrivals are authority movement receipts.

## Interruption and privacy

Invitations, decisions, movement and completion survive restart. A stale or
cancelled stage cannot be completed; other actors cannot use an invitation or
receipt. Old arrivals cannot satisfy a new acceptance. No missing receipt is
converted into success. Stale offered invitations are cancelled when the role
is otherwise filled or the stage closes.

An accepted NPC may withdraw. The board displays this, preserves completed
human reports, and does not silently replace it or credit arrival. The party
can cancel the run. Likewise an unsupported or interrupted NPC plan may leave
the stage waiting; there is no timeout victory or automatic forced movement.

NPC invitation context contains only public destination facts, not the private
party transcript. NPC completion receipts expose only their own arrival. The
human party privately sees the NPC's role status. No player save is rewritten.

## Scope and ancestry

NPC invitation currently requires a reachable different destination on the
NPC's current generated map, using the existing 64-step route executor. It is
not cross-map NPC assignment or ordinary-Hoenn movement. Players may normally
travel to any supported exact generated revision for their own visit roles.
No carrying, player warp, reward or simultaneous arrival is implied.

Separate branch on #391 head 1d7cbd0782ba5f121ed77114d3f02a6ea3d80221.
Native #56 remains 739be20ecf1101f84cc2fb272587978350955b6d. Not RC12-based.
Frozen #384/#56, Maya's integration and all denied uploads stay untouched.
No live providers used. Component movement tests run the actual authority
reducer, with fixture admission rather than a rendered or linked-native test.
Final game/client integration remains unverified and belongs to Maya.
