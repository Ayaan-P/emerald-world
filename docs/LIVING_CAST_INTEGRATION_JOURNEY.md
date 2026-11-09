# One connected living-cast integration journey

This is a proposed authored QA scenario, **not a fixed shipped storyline or proof
of live model output**. The candidate provides reusable affordances; an enrolled
host author chooses whether to use them from real allowed history.

## Pair to review

- App draft: Ayaan-P/emerald-world PR286, `dot/rc12-living-cast`.
- Engine draft: Ayaan-P/pokeemerald-expansion-native PR26,
  `dot/rc12-canonical-cast`, commit
  `4f9e1a83a029b31486419e3f36bd4d63492080ba`.
- The app's engine gitlink remains
  `488796e4959eb7f9d658abc7e8313e138acb3c87`. A build from that unchanged pin does
  **not** contain the current scene/call/partner candidate. Maya owns deliberate
  integration, pinning, full native build, rendered QA and release.
- Main was inspected at `80b14ebfbfd4dd4da2dc16d886a37f0db1f45516`; neither draft
  had been merged when this batch was prepared. Reconcile any newer work first.

## Player journey

1. Two trainers continue their own Emerald saves. Original progress, parties and
   services remain independent. Real explicitly shared campaign/field events can
   inform an already configured cast author; private history is not automatically
   published to that author.
2. The author lets Rydel reconsider a goal, offers a speaker-led shared question,
   and optionally offers the reviewed `rydel_step` scene. These are choices in a
   versioned canonical action, not a required arc. Original Rydel is still the
   Bike Shop NPC; there is no duplicate roaming Rydel.
3. A trainer talks to him normally. His original bike service remains intact.
   The supplemental field message can open the existing SELECT conversation
   panel. A speaker chooses; other trainers optionally listen and offer advice.
   Advice is not a veto and the speaker's choice is not unanimous agreement.
4. If everyone wants the brief demonstration, all connected trainers gather in
   the Bike Shop. After the current Rydel conversation, one uses `/history scene
   ask`. Each receives a private invitation and explicitly joins. The original
   Rydel takes one real native step and returns, with observers synchronized at
   each step. B cancels. No trainer is dragged from another map, and no follower
   flag or new Pokémon is manufactured. Ordinary controls/service resume after
   verified local restoration.
5. Actual public conversation decisions and committed shared project actions can
   inform later agent choices. For example, another actor can independently
   contribute to an executable project, change available `/story` interactions,
   or form a directional assessment of a real public choice. These are authored
   possibilities, not preinstalled outcomes. The scene itself currently publishes
   no completion/relationship credit, so the author must not claim it happened.
6. Separately, already registered Wally or Steven can make optional native Match
   Calls when their current authored record requests one. Original phone calls
   retain priority; players answer, decline or use quiet mode. A call does not
   assume the recipient attended the group scene or expose private conversations.

Later, the same reviewed engine primitives can support larger original-cast
scenes. Current physical execution is deliberately just Rydel's verified room and
closed path; it does not yet provide arbitrary canonical travel or schedules.

## What has been exercised

- 264 focused app/component tests cover the cumulative candidate; final focused
  scene/lease/initiative/cast rerun: 42 tests passed.
- 20 native component/source tests pass, including the production scene controller,
  actual CORE negotiation and existing character adapter tests.
- Two compiled production native scene controllers exchange their emitted packets
  with the real authority dispatcher. Tests exercise all-participant barriers,
  step acknowledgements, cancellation, occupied paths, restoration, server restart,
  save-lineage fencing, disconnect and stale/early messages.
- The fixture explicitly doubles engine globals, collision responses and sprite
  movement. Source inspection also verified the exact real map floor tiles and
  the actual collision-function insertion points. This is **not** rendered or
  full linked-engine verification, and deterministic authors are not live models.

## Maya's integration/playtest pass

Build the exact paired engine, then run two to four real clients with independent
saves. Verify ordinary bike exchanges before and after the scene; old-client/old-
server refusal; one player declining; player standing on the path; each observer's
real animation; B during each step; late connection; dropped connection; server
restart; native process restart; save/reload; unexpected field-script ownership;
and return-to-room recovery. Confirm missing recovery blocks only another scene,
not ordinary gameplay. Check phone/script/scene interactions and actual chat input
closure. Do not infer those outcomes from the component harness.

No merge, deployment or release was performed by this work.
