## Voluntary companion exchange
This continuation of #322 uses the unchanged native #35 battle descriptor path.
No autonomous capture capability is advertised: the inspected native worker
supports INIT1/STEP1 and daycare-like bounded practice, not a wild-battle/capture
resolver with AI, balls and durable catch outcomes.

Instead world.offer_companion and world.respond_companion let two adjacent idle
world-owned characters independently agree to transfer an existing benched
individual. The configured author sees pending offers and actual owned rosters.
Acceptance rechecks ownership, exact offered state, co-location, active battles,
recipient capacity and identity conflicts. Decline/withdraw makes no transfer.
No canonical actors or player Pokemon are eligible; active teams are untouched.

Atomic custody moves preserve species, personality, original trainer and any
engine-bound full practice state. Historical donor rows remain provenance, not
usable inventory. Ownership guards prevent donor challenge/practice resurrection.
The recipient can later choose the received individual with the existing generic
prepare_challenge capability, which feeds the normal authenticated native party
descriptor. This is a handover, not native trade animation or trade evolution.

Tests use supplied plans and fixtures: independent offer/accept, restart,
decline, unavailable recipient, invented individual refusal, unchanged native
identity in actual challenge wire and exact opaque full-state preservation.
They do not prove a native-generated catch, rendered battle or live model choice.
Native capture/simulation and rendered integration remain unimplemented/QA scope,
not silently substituted with invented successful catches.

---
## Destination-based linked navigation
This continuation of #321 keeps paired native #35 unchanged.
world.navigate_places takes destination place ID, exact cave revision and x/y.
The runtime exposes the real installed directed cave-link graph, finds a route,
then persists a coordinator that invokes existing world navigation and traversal
executors one leg at a time. Agents do not supply paths or named scenarios.
Actual leg outcomes are retained and final completion requires the actor at the
requested tile under the requested revision. No player save or warp is changed.

The coordinator survives restart, revalidates links/geometry, and refuses an actor
that moved or changed outside its journey. Occupancy can pause native-supported
walks; an unavailable path or changed link blocks with a replan result, rather
than automatically retrying forever. A withdrawn plan stops dispatching new legs;
already-admitted walking uses existing interruption rules, not a forced rollback.
Routing is limited to opened plain/Expansion wildlife caves and existing directed
links, with the existing 64-step per-map path bound. It is not Hoenn/canonical
travel, outdoor REGION1, seamless streaming or a rendered-animation claim.

Composition uncovered a source-control precondition defect after prior walking:
traversal now compares the authoritative controlled actor object, not the base
script's stale initial object. Only the exact previous verified dispatcher is
migrated; arbitrary changed source is still refused.

Tests execute a three-cave journey with two real traversals and local walking,
restart midway, another actor/destination, removed link and withdrawn plan.
Native scoped observer behavior is inherited from #320's paired tests.
Maya remains responsible for integrated rendering/multiplayer/provider QA.

---
## Sustainable character executor
This continuation of #320 removes the new-action lifetime ceiling without
raising it. compile_actions now emits one verified reusable dispatcher. Each
subsequent command replaces only its literal request and bootstrap checkpoint;
the current receipt rotates rather than accumulating source wrappers.
Existing append-only wrappers and their receipt lists remain untouched, including
a full 32-item legacy list, so previous commands cannot replay.

Every newly admitted command is verified against the actual before/after actor
version, character record, object/control and command hash, then archived in
SQLite and public causal history in the same transaction as mechanic admission.
Rejected staging cannot archive success. Pending cave traversal can find its
committed receipt after rotation/restart. Navigation, actor actions and traversal
share this mechanism. Authored source with a modified reserved dispatcher is
refused rather than silently rewritten. Existing per-request/state/source size
limits remain; durable history grows on disk, not as an ever-growing wrapper.

The cave source/arrival occupancy guards are now declarative action preconditions
inside the reusable executor instead of appended special-case wrappers.
Tests perform 40 admitted actions with bounded source and one current receipt,
restart halfway, verify all 40 archive records, and verify no replay. Full legacy
receipt preservation and modified-dispatcher refusal are also tested.
Native stays #35; no game rendering or live-provider QA is implied.

---
## Independent actor cave traversal
This branch continues #319 with no native changes: paired native #35 remains
1f7a2e52212d9f6ba69acda70ef3f96e044285e5.
world.observe now reports actual cave-link destinations on nearby props.
A world-owned character may compose world.navigate with world.traverse_link,
using the observed object ID and program_revision. It must be adjacent and idle,
with no pending player battle. Canonical actor bindings cannot call this tool.

The existing character-action executor stages a versioned relocation through
normal mechanic admission. The same identity, team, relationships and plan are
retained. Source observers receive removal; destination observers receive the
actor through existing exact-revision native object snapshots. An entrance
neighborhood tile is chosen from actual validated geometry, avoiding objects,
player entrance and ready players; concurrent occupancy fails admission.
The durable tool result is emitted only after the committed state is verified.
A link installation or pending deployment never counts as travel.

This is an authority portal transition, not a walk animation, elapsed-time
journey, player warp, catch or canonical story change. Agent-authored decisions
remain model-dependent; tests use supplied plans. Source staging still inherits
the existing character-action source/receipt consolidation bounds; this adds no
background movement scheduler or infinite-growth claim.
Four focused travel tests cover two actors, source/destination observer snapshots,
retained team/identity, restart, unadmitted staging and concurrent occupancy.
Rendered multiplayer and full native QA remain Maya's responsibility.

---
## Habitat-link continuation
This branch continues #318, pairing native draft #35 at
1f7a2e52212d9f6ba69acda70ef3f96e044285e5. It overrides the prior pin below.
The same world.link_caves primitive now accepts already-opened Expansion wildlife
caves (format 10), with separately negotiated CAVELINKW1. Existing population
authoring can place real revision-bound characters/props in these caves, enabling
return links rather than a one-way habitat dead end. Plain-only clients cannot
initiate a wildlife transfer. Wildlife-capable but old link clients also refuse.

Native reload validates the complete species/level table before changing source
state; installs destination encounter profile and shared wildlife, or clears
them when returning to plain geometry. It preserves the original Hoenn return
warp. Authority restart/reselection preserves the exact encounter bytes and
requires a new ACK; it does not invent a completed trip or restore stale presence.
No caught Pokemon, training result or player-bag mutation is generated here.

Focused paired tests: 12 authority/decoder cases and the actual C transfer/
wildlife validator fixture pass. Broader component suite is separate; native
rendering, random encounter battles, capture/save/reload and reconnect gameplay
remain Maya's integration QA. No live-provider call, merge or release.
No large-cave or outdoor selectable-region admission changes are included.

---
## Cave-link continuation
The current dot/cave-link-transfer candidate includes #315–317 after the consolidated
#314 baseline described below. Its paired native is draft #34,
97ea17b0fb3fa221327950bd1da820e1dbed4d0d, based on #32. The gitlink,
builder PIN and manifest agree. This overrides the historical pin below.

Agents discover world.link_caves: observe an anchored prop in an immutable plain
cave, bind its observed program revision to another already-opened plain cave's
exact place ID and digest. Existing actions/programs cannot be overwritten.
Players approach that actual prop and press A; native asks whether to travel.
Accepting downloads into a separate decoder, verifies the hash, acknowledges,
then reloads the destination at its entrance. The original Hoenn return warp
is retained. Other players remain in their own admitted caves. A reverse link
must be authored separately. This is an object-triggered transition, not seamless
terrain, and uses existing prop graphics rather than new portal artwork.

Requires --generated-regions and a CAVELINK1 client. Only format-1 caves are
supported. No outdoor selectable-region admission changes are included.
Rejected/stale transfers cannot fabricate arrival. Abort before reload restores
source admission with fresh readiness required; uncertain post-commit timeout
disconnects rather than guessing completion. Recovery/reconnect and return-warp
behavior still require rendered integration QA.

419 component tests passed (2 sandbox-dependent skips), including authenticated
server interaction, independent peers, restart, abort and real native decoder
fixtures. Native transfer function test verifies source preservation and return
warp invariants with engine API fixtures. No full linked build, live provider
execution or rendered multiplayer playtest is claimed. Maya owns integration/QA.

---
# One capability candidate for integration

Use the head of app draft #314 (`dot/practice-session`), not a selection of its
incremental PRs. It contains #299, #300, #301, #303–#313 on the #286 living-cast
base f81be46b6d9296e2710563af5878b3d4500b0b4e. GitHub comparison verified every
listed head is an ancestor. #302 is Maya's independent integration branch, not a
missing link in this chain. Do not merge/rebase it or substitute its native pin.
Main was 80b14ebf; #302 was 5f486397 at this audit. These are observations, not
integration instructions that override later work.

Paired native: PR32, 30a4fae1b19340225926d350895a30e516615a8c. App gitlink,
builder PIN and manifest agree. No native changes in this consolidation.

## Connected journey

1. Initialize the pinned submodule and build with
   `python3 scripts/build_expansion.py --generated-regions` (plus existing
   sysroot options if needed). This enables the actual REGION1 place picker.
   It does **not** enable regional saves/Kanto. Build frontend normally and run
   `python3 -m world.web_launcher --engine expansion-native`.
2. Host a local world; normal independent trainer profiles and campaign remain.
   In Living Cast, explicitly choose Anthropic Messages or OpenAI Responses and
   an exact available model ID, with the corresponding host environment key.
   No key is entered into the launcher. Initialize/follow canon seeds, then start
   the author. This is not a shipped deterministic story or guaranteed response.
3. Give an enrolled actor a natural-language goal. The configured provider sees
   actual state, capability catalog and committed results. It can choose plans
   to create a place, then use returned revision to populate it, observe, navigate,
   address another NPC or manipulate supported props. Each result is authoritative;
   author request completion alone is not world completion.
4. Players select opened plain cave/CAVE10 habitats through the existing place
   picker and entrance. Plain caves support persistent characters/props; CAVE10
   habitat population is wildlife, not yet dynamic NPC/prop placement. Outdoor
   layouts use the one shared XL slot, not multiple selectable outdoor regions.
   Occupied/populated slot replacement is refused. No seamless portals claimed.
5. Enable recurring automatic NPC authors before an agent populates new characters
   if independent child lifecycles are desired. New identified teams are authored
   baselines, not catches. Optional challenges use native player consent and stable
   owned lineups. Props only execute advertised bounded handlers, not player bags.
6. Only after exact linked-binary isolated-entry QA, enable the advanced practice
   worker with that binary's digest. Recurring budgets bound execution. Reconciled
   full Pokémon state feeds later optional challenges. This is isolated exercise,
   not simulated battles/evolution. Stop/withdraw controls do not undo past effects.

## Boundaries for Maya

Component/fake-provider/native-adapter fixtures pass, not a rendered multi-client
acceptance test. Two full-worker fixtures skip the exact Bubblewrap loopback
NETLINK_ROUTE restriction here; no bypass was attempted. No live model/credentials
were used. Linked build, selectable-region UI, host/socket worker lifecycle,
real-provider open-ended plans, and multi-client play remain integration QA.
The supported build option fixes a previously unreachable place-picker path; it
is not proof that the feature has been played. No merge, release or auto-deploy.
