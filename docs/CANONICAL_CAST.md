# Original cast, public activity, evolving intent

The first reviewed canonical binding is Rydel's original BikeShop script.
Unlike world overlay characters, `canonical_cast.canon_rydel` creates no object
and has no team, item, flag, travel or battle effect. Its bounded supplemental
line runs after the original lock/faceplayer, then original bike choices and
exchanges continue unchanged. Offline, missing authored state, older authority,
refusal or timeout continues the ordinary script.

An agent may return `canonical_actions` and tests through the existing GM. Each
single action identifies `canon_rydel`, an expected version (0 for first authoring)
and changes containing goal, literal ASCII dialogue (200 characters maximum),
1..4 known native places of interest, exact public activity evidence and reason.
There is no predetermined arc. Normal author tests, sandbox and atomic admission
still apply. Evidence must be committed opted-in `guild_goal_completed` history
in those interests, not a private save observation or invented personal victory.
Neither the initial record nor later decisions duplicate the original NPC.

After the initial explicit authoring, the host can use the existing
`runtime_gm follow-character --id canon_rydel` workflow with a purpose. Its
configured runtime then reacts to new real public activities in those interests.
The author can choose a new goal/response or wait; only this actor's typed action
is accepted. Player purposes and party observations are removed from this
public reaction context. Decisions are durable and appear in the existing
world journal as authored interpretations linked to their actual evidence.
They do not claim that Rydel personally completed someone else's expedition.

The native adapter sends `CORE run CAST rydel safe nonce` only at that original
script safe point. The authority checks authenticated CORE1 negotiation and
fresh BikeShop location, then supplies the current immutable response digest.
Existing run/world/nonce validation rejects stale or mismatched replies. CAST
needs no Devon completion or bike entitlement; original scripts alone decide
what the player may receive. No private progress is inferred from public results.

## Pairing and limits

Requires the paired native canonical-cast patch atop native PR25 at 9d4635b0.
Current app gitlink 488796 does not contain that hook. This app branch intentionally
does not change the pin or claim deployed/rendered behavior. Maya owns pairing,
full build, gameplay QA and release. Wally in Wanda's house and Briney in his Route104 house now share the reviewed
lock/faceplayer adapter. Their ordinary speech and sailing scripts are unchanged.
Automatic cutscenes, Wally battles/rematches and Steven are not intercepted.
No namesake actors are spawned as a substitute.

Tests use real guild authority, two actual public completions, persisted actor
revisions and authenticated CAST dispatch; the exact authority packet enters the
compiled production native adapter. Native component tests cover original script
continuation, legacy refusal, nonce/world checks, timeouts, save-lineage storage
and untouched bike script bytes. A full linked/rendered RC12 build has not been
performed in this environment. Reaction author outputs in tests are deterministic
fixtures, not evidence of a live model run. The existing 32-action consolidation
limit applies. No merge or deployment is included.

## Optional field proposals and multiple original actors

`canon_rydel`, `canon_wally` and `canon_briney` use the same bounded action
contract. An action may include `offer: {map: "LittlerootTown", count: 2}`
(or null to stop offering). The destination must be a native place in that
actor's interests. This is a proposal to players, not proof of an NPC journey.

The original actor's supplemental response points to guild chat. At the actor's
native location, `/guild cast wally` privately previews the exact destination,
trainer count and public nature. `/guild cast wally VERSION` explicitly accepts
the previewed version. Existing guild rules enforce leader permission, existing
chronicle consent, membership count and no conflicting expedition. No automatic
warp, publication opt-in or new NPC is created. The native guild-command guard
keeps this command out of public fallback chat on older servers.

Authenticated ready visits complete the existing expedition. Its frozen receipt
records the original actor and proposal version; repeated acceptance cannot
award another reward. While an actor has an offer, only that exact offer's public
completion queues its next author turn. Wally cannot claim Briney's result.
The author then chooses new terms, withdraws the proposal, or waits, based on
the inspected outcome. An older accepted expedition keeps its original terms
even if the actor changes; a stale accept is refused. This does not infer that
Wally fought, Briney sailed, or anyone trained off-screen.

Current checks: 91 app/author tests plus three compiled native component tests.
The new test uses two original actors, explicit private preview/public consent,
real authority visits/rewards, typed next action, actor isolation and replay
protection. No live model, full linked native build or rendered QA claim.

## Directional cast relationships

Actions may additionally contain `relationships`, keyed by up to two other
already-authored canonical identities. Each relation has a `stance` (curious,
encouraged, concerned, respectful or competitive), bounded literal `motivation`,
and 1..4 evidence sequence numbers also present in the decision's evidence.
Each source must be a real opted-in public completion of that target actor's
field proposal, in this actor's declared places of interest. A player name,
self-reference, uncreated actor, generic unattributed activity or fabricated
meeting cannot establish a relationship through this contract.

These are explicitly one-way authored interpretations. They do not declare
mutual friendship, private player affinity, NPC travel or a simulated meeting.
A followed actor with a relationship can reconsider its own goal, dialogue or
proposal after a new actual result from that target, even while it has its own
proposal. Actor edits alone never trigger the loop. Existing queue cursors,
version checks, exact history rereads and bounded author response rules apply.

`/guild cast wally thoughts` privately shows the current authored goal, directional
assessments and public evidence references at Wally's original map. The original
native talk response reflects the newly authored dialogue. No new native payload
is required. A regression follows Rydel's real completed proposal, Wally's
curiosity, a second real result, Wally choosing encouraged shorter practice and
withdrawing his proposal, then persistence across authority restart. No extra
XP or reciprocal Rydel relationship is manufactured. Deterministic test authors
exercise the production pipeline; autonomous live-model behavior remains QA work.

## Independent private conversations

An authored actor may expose `conversation`, a dictionary of up to three choice
IDs. Each entry has a literal `label` (48 characters) and `reply` (200 characters).
The labels and replies are public authored content, grounded in the same public
activity evidence as the actor's decision. Actual player selections are private.
No free-form player text or personal attributes enter this authoring contract.

At the original actor's map, `/guild cast rydel talk` previews the options and
privacy scope. `/guild cast rydel talk VERSION CHOICE` explicitly selects one
for the authenticated trainer only, without requiring guild leadership or guild
membership. The authority privately returns the answer and the same original
NPC's next native CAST response uses that trainer's selected reply. Another
trainer can have a different conversation at the same time. Neither pauses,
alters or claims the other's canonical progress. No host narrative ownership.

Selections live in a dedicated private authority table keyed by trainer and
actor, not world state, world history, journals, public reaction context or other
players' snapshots. They survive reconnect and authority restart. They are per
trainer identity, not per save lineage. `/guild cast rydel forget` deletes only
your selection, anywhere, including when busy. An actor revision invalidates
old selections until you explicitly choose again, so updated authored content
cannot silently reinterpret your earlier choice.

This is bounded conversational agency, not a simulated hidden affection score
or an LLM reading private play history. Responses are authored alternatives;
there is no player-specific model generation. Shared decisions can revise these
alternatives, but private choices never trigger a public author turn or reward.
Tests cover concurrent independent choices, private native reply, no inspection
or history leakage, persistence, stale revisions, impersonation, invalid input,
forgetting, and production C consuming the exact selected authority packet.

## Character-initiated public correspondence

A canonical action can include `letter: {to: "canon_wally", text: "..."}`.
The recipient must already exist in authored canonical state, must be a different
bound actor, and text is limited to 200 literal characters. At atomic admission,
the authority records `canonical_letter_delivered`, its sender/version,
recipient, text, source evidence and reply depth. This is a real persisted
in-world message, not a simulated physical meeting or external communication.
It appears in public history/journal and `/guild cast ACTOR letters` (latest
three exchanges), and can be recalled by the recipient's configured author.

The sender chooses to write based on its existing public evidence and intention.
A followed recipient receives a bounded author turn for that exact delivery,
not for an arbitrary actor edit. It may adjust its goals/dialogue, reply, or wait.
The reply can in turn inform the original sender. At most two deliveries are
allowed in a reply chain: the next turn must clear the letter field and reconsider
its goal or wait. Exact evidence/version checks prevent a reaction from ignoring
its trigger to reset the chain. No scheduler is started automatically. Old source
ticks and unchanged letter payloads do not redeliver. Authority restart preserves
both correspondence and interpreted growth.

Letters are public fiction, never free-form player messages or private choices.
They grant no tool permissions and cannot establish a fabricated battle, trip,
meeting or mutual relationship. A new unrelated public activity can independently
motivate another exchange. No inventory, reward, travel or personal save mutation
occurs. The end-to-end regression sends Rydel's actual letter, schedules Wally's
agent turn and reply, then Rydel changes his encouragement goal with no intervening
player chore or reward. These test authors are deterministic; full native rendered
QA and live-model behavior remain separate checks.

## Executable character projects

An actor may publish a playable practice course with:

    project: {kind: "petalburg_relay", title: "Patient Practice", limit: 240, mounted: false}

The actor must include PetalburgCity among its interests and supply inspected
public evidence as for other decisions. This first project adapter intentionally
uses the existing Petalburg checkpoint/handoff layout; the character controls the
name, time budget and mount requirement, not arbitrary unverified map geometry.
It is a reusable activity design, not a claim that the NPC physically constructed
a track or completed a race. Further project kinds need their own safe adapter.

Admission validates through the production relay validator and atomically installs
an immutable course plus an actor ownership/digest receipt. It appears in the
existing activity board and `/guild cast ACTOR projects`, which shows direct
`/guild relay start ID` commands. Native actor dialogue points to the practice
courses. Players join and ready explicitly through the existing relay interface.
The usual actual checkpoint order, adjacent baton handoff, authority timing and
private record persistence apply. There are no item, save, terrain or reward edits.

Successful installation creates `canonical_project_published` evidence with exact
content digest. The character can cite that real achievement in correspondence,
and other agents can reconsider their intentions after reading the delivered
letter. Publication alone does not enqueue new automatic author turns, preventing
self-generating project loops. Private race participants/times do not enter this
public evidence. Existing runs keep their immutable course; a new design gets a
new identity. Repeated content is not republished. Operator-owned course collisions
fail closed and roll back the character revision, history and installation together.
Eight projects per actor and the existing 64-course global cap bound growth.
Removing a project from current intent does not delete the previously published
course or invalidate player records.

Validation includes a full in-memory production relay CHAT/STATE run of Rydel's
new course, both runners' readiness, actual checkpoints and handoff, saved private
time, followed by Rydel informing Wally of the actual publication and Wally
reconsidering his goal. It also covers restart and atomic collision rollback.
110 focused app/author/relay/activity-board tests pass. Rendered native gameplay
and live-model initiative are still not claimed; Maya owns paired build and QA.

## Social project participation and owner decisions

A character can propose `contribution: {course, digest, text}` for another
existing actor's installed project. The exact public publication must be among
the inspected evidence. This is authored practical guidance, not a claim that
the contributor raced or attended. One immutable contribution per actor/project
bounds duplicate work; the three supported cast identities imply at most two
contributors to a project. Player/private race data is never copied.

Authority proposal delivery queues a turn for the project's followed owner. The
owner can independently choose `resolve_contribution: {seq, decision}`, where
`decision` is `accept` or `decline`, citing the exact proposal. Only the real
project owner can resolve an outstanding proposal. A decision is not inferred
from friendship, public reputation, guild leadership or player progress.

Acceptance publishes the contributed text into the actual activity briefing.
The existing relay start/join commands show it to participating players; existing
runs retain their start-time briefing snapshot. No player is joined automatically,
non-participants receive no unsolicited messages, and declining publishes no
guidance. The resolved decision becomes exact evidence for the contributor's
next configured author turn and can change its actual goal/dialogue. Authored
changes alone do not sustain an automatic loop. Both parties may wait instead.

The test executes Wally's proposal, Rydel's independent acceptance, actual runner
start/join with Wally's adopted advice, Wally's resulting goal change, and restart
persistence. Separate cases reject wrong evidence/digest and self-resolution and
exercise a real decline. This extends the existing project rather than creating
another race variant. It does not simulate physical attendance, training or
private player-specific AI. 112 focused app/author/activity tests pass.

## Retained intentions and bounded initiative

A character can retain up to three concrete intentions, each with `id`, `kind`,
`target` and `reason`. Supported kinds are `letter` (target another existing bound
actor), `project` (target `petalburg_relay`) and `contribution` (target exact course).
These are pending work, not outcomes. Existing `follow-character` enrollment and
an explicitly configured author runtime are required; no model is started by
saving an intention.

When that followed actor has no event turn pending, its runtime may enqueue the
next retained intention without another player event. The author either waits or
returns a typed action with `fulfill: TASK_ID`, removes it from pending work and
performs the exact supported action. Authority completion requires a newly committed
letter/project/contribution receipt in the same transaction. No-op publication,
wrong target, fake completion or previously completed task rolls back. Actual
completion becomes evidence for one further goal-reflection turn, so a character
can change its intention after its own work rather than only other people's chores.

Attempt records survive runtime restart. Each task ID is attempted once, even if
the author is interrupted or chooses to wait; there is no silent retry. Pending
work remains visible in `thoughts` until deliberately revised/abandoned or fulfilled.
The candidate caps initiative at eight attempts per actor/world in that runtime
state. It does not automatically refill the budget or invent new work to bypass
it. Public-event reactions still operate normally. Long-running host-controlled
budget renewal is a separate future feature, not an unlimited autonomous loop.

The regression retains Rydel's intention to ask Wally about his priorities, queues
it with no new world/player event, executes the actual letter, verifies its action
receipt, and then revises Rydel's goal to wait for Wally. Restart preserves the
completion and does not replay it. Interrupted attempts remain pending without
retry; unrelated changes and invented fulfillment are refused. 114 focused tests
pass. No native travel, training, battle or save mutation is implied.

## Real private encounter memory at the original NPC

Reassessment: current main remains RC11 baseline 80b14ebf; this candidate is not
merged and its default native pin still lacks the paired cast adapter. Existing
features provide author/runtime capabilities, not fully simulated canonical
travel or Pokémon lives. The new paired adapter closes a specific actual gap:
remembering a trainer's encounters with an original character.

`/guild cast rydel remember on` explicitly enables private encounter summaries
for this trainer and actor, separated by the native save lineage. It does not
publish history or give the shared-world author access to private interactions.
After the production native field-message function successfully opens a CAST
reply, the client sends a fire-and-forget `SEEN` receipt for its exact response
challenge. Only a fresh, matching, unconsumed receipt from that authenticated
connection/run/map records the encounter. Merely requesting dialogue, timing out,
replaying an old digest, another connection or a different save does not count.
The receipt never holds the native request slot or delays the original script.
Old clients continue normally but cannot create verified display summaries.

A repeat encounter in the same save receives a familiar greeting. The summary
retains count, last actor version/goal and exact shown reply, not a psychological
score or inferred affection. Counts reflect client-acknowledged message display,
not proof that the player read it; this is not an anti-cheat primitive. Each
trainer/actor keeps at most the latest sixteen save profiles, with one bounded
summary per profile. Another trainer and a new save begin independently.

`/guild cast rydel memory` shows only your private summaries. `remember off`
pauses collection and familiar greetings while retaining prior summaries.
`forget` erases your choices and encounter summaries and disables remembering,
without affecting anyone else; forgetting is available away from the actor.
The existing public world history, journal and author inspection remain identical
before and after personal encounters. The authority operator still owns its local
storage; this is application-level isolation, not encryption from the host.

116 focused app tests and three compiled native tests pass. The paired regression
feeds the actual authority reply into production C, executes its message hook,
feeds the emitted SEEN line back through the actual authority, then verifies the
next private greeting. It also covers replay, expiry, save/connection isolation,
restart, pausing and forgetting. Full linked/rendered RC12 and live-model behavior
remain unverified. This does not add autonomous travel, Pokémon ownership or a
Steven hook.

## Explicit private character interpretation

`/guild cast rydel reflect` previews a single summary: character/current goal,
acknowledged talk count, last shown reply and actor goal, and any currently valid
explicit conversation-choice label. It identifies the host-configured OpenAI
character model and local host access. Nothing is queued or sent merely by
previewing. `/guild cast rydel reflect confirm CODE` authorizes that exact snapshot
once; changes or expiration require a new preview. Party, save identifiers, trainer
identity fields, other chat and other players are excluded from the model input.
Displayed text itself is included exactly as previewed, not silently redacted.

A separate operator-invoked worker processes one authorized request:

    python3 -m world.private_cast_worker --socket ADMIN_SOCKET --model gpt-6-luna

It uses the existing pinned, ephemeral, tool-disabled Codex adapter in an empty
temporary directory, with a separate reply/interpretation schema. It never fetches
world inspection, history, previous source or player records and cannot deploy
world code. Prompts and replies are not written to shared author artifacts or
printed to logs. No model starts automatically. Pending requests are atomically
claimed once; a failed/interrupted worker does not replay them. A new explicit
request replaces the prior request for that trainer/actor.

The model may produce only bounded literal `reply` and `interpretation` strings.
Instructions distinguish explicit player choice from mere display acknowledgment
and prohibit invented feelings, traits, achievements or private events. This is
an authored tentative character interpretation, not an objective psychological
judgment. Validation prevents tool/source output and any gameplay/state effects.
The current actor version, remembered interaction and choice must still match
before application. The resulting reply is shown only to that trainer/save through
the existing original NPC hook; after another acknowledged conversation it is no
longer reused. Its private interpretation/status is available via `reflection`.

`remember off` or `forget` cancels pending work and removes private interpretations.
A late worker result is rejected. Data already handed to the worker/model cannot
be recalled; cancellation prevents further application, not past transmission.
World state, public journal/history and other trainers remain unchanged.

119 focused tests pass, including explicit preview/confirmation, actual admin
claim/finish dispatch, deterministic isolated worker response, next native reply,
restart, withdrawal, stale snapshots, cross-player/save isolation and refusal of
world-code/tool outputs. No live model call was made for these tests. The existing
paired native adapter is unchanged; full rendered/live-model QA remains separate.

## Persistent individual Pokémon in the existing dynamic battle adapter

The dynamic-trainer factory previously regenerated every opponent with a random
personality each battle. Teams in the existing `world_characters` registry may
now identify every member with a stable `individual` ID alongside species/level.
An immutable authority archive derives and retains each individual's personality
and fictional trainer ID independently of slot, team version or level. Removing,
reordering and later restoring the same companion preserves those identities.
The archive is scoped to the world and character, with 32 individuals per actor.

The matched native client negotiates `CHARPK1` and receives a frozen
`CHARACTER_BATTLE_V2` descriptor. Its production factory uses the actual RC12
`CreateMonWithIVs` API with preset owner/personality and the existing 15-IV balance,
then initializes the native level-appropriate moves. OT name/gender are explicitly
set to the fictional trainer rather than inherited from the player's save.
Only `gEnemyParty` is constructed; normal trainer scripts and player party/storage
are unchanged. Old un-identified teams still use V1. Old clients refuse identified
teams rather than silently turn persistent companions into random replacements.
Capability fallback drops CHARPK1 before earlier optional roles.

This is individual continuity in actual dynamic opponent construction, not earned
XP, simulated catches, persistent injuries or autonomous training. Levels remain
author decisions grounded by the existing history contract. Species cannot change
for an archived ID until an actual supported evolution adapter is added, including
after removal/reintroduction. Unsupported cross-species reassignment fails closed.

This slice applies to already-supported agent-authored recurring NPCs. It does
NOT attach a new team to canonical Wally/Steven or replace their story battles.
Those actors still need a safe optional sparring interface; metadata is not that
interface. The native component test compiles the production factory/parser with
engine fixtures, exercises all six opponents, reorder/level changes, preset OT,
legacy random behavior and malformed/overflow refusal. It is not a full native
Pokémon arithmetic/build/rendered playtest. Authority tests verify frozen pending
teams, restart, older-client refusal, archive reuse and identity isolation.
