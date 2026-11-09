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
