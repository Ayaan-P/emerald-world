# One connected living-cast integration journey

This is a proposed authored QA scenario, **not a fixed shipped storyline or proof
of live model output**. The candidate provides reusable affordances; an enrolled
host author chooses whether to use them from real allowed history.

## Exact draft pairing and setup

- App PR286: `dot/rc12-living-cast`; engine PR26:
  `dot/rc12-canonical-cast` at `f5b45730ef96debf512f501109b3388ab2342cc6`.
- This draft now pins that exact engine in both its gitlink and builder. Standard
  submodule initialization/build no longer silently uses the older 488796 engine.
  Main and Maya's integration/release branches are not changed.
- Main was rechecked at `80b14ebfbfd4dd4da2dc16d886a37f0db1f45516`. Both drafts
  remain unmerged. The paired engine is 19 commits ahead of the old pin with no
  divergence. Check for newer integration work before applying this candidate.
- See [RC setup](LIVING_CAST_RC_SETUP.md) for explicit host author enrollment,
  prerequisites, player entry points and the real live-author/native-build gaps.
  `engines/living-cast-candidate.json` is the machine-readable pairing manifest.

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

- 275 focused app/component tests covered the paired field-project candidate;
  setup/pin checks are additionally reported with the latest commit.
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

## Optional continuing personal responses

The companion document [Ongoing private cast responses](CAST_ONGOING_PRIVATE_RESPONSES.md)
adds an optional per-save standing grant and explicitly bounded host worker.
After a shared choice, Alice's advice and Bob's speaker decision can lead to
different next original-NPC replies without another confirmation for each turn.
This is private interpretation of actual choices, not autonomous physical action.

## From an autonomous project to an original-character activity

[Project activity bindings](CAST_PROJECT_ACTIVITIES.md) let actual independent
cast contributions make an existing native invitation available. The tested
path is Steven opening a project, Wally independently contributing, then the
player meeting original Steven and requesting his existing optional partner
encounter. There is no intervening player errand or author turn required to
expose that consequence. Project work is abstract social state, not claimed
physical travel or training. Native battle QA remains outstanding.

## Play the actor's changed project without leaving normal dialogue

The [native project panel](CAST_NATIVE_PROJECT_PANEL.md) exposes actual local
player choices from the original actor's owned initiative. START opens it,
SELECT pages, A chooses and B returns to the normal script. An independent actor
turn can change what appears on the next visit. Only the actor's current map is
accessible; private character replies are not mirrored into the project.
