# Living-cast RC setup and handoff

## Pair, do not mix branches

App PR286 now pins engine PR26 commit
`f5b45730ef96debf512f501109b3388ab2342cc6` in the submodule and build script.
The manifest is `engines/living-cast-candidate.json`. This changes only the draft;
it neither merges the feature nor releases it. Maya should reconcile newer work,
initialize submodules in a dedicated integration checkout, and use:

    python3 scripts/build_expansion.py --check
    python3 scripts/build_expansion.py

Existing sysroot options remain available; the builder installs/downloads nothing.
Do not reset dirty engine sources or use a player's live save for integration.
Normal clean-pin checks, ABI probes and sandboxing remain mandatory. The native
source is a clean descendant of the previous pin, not a partial-tree replacement.

## Launcher entry point

In the Expansion React launcher, open Local worlds → Living cast for the desired
world. Open that local host, select Anthropic or OpenAI and an explicit API model,
review the data/cost notice, then start the world author. Use Initialize and follow original cast for the one-step first-cast setup below.
The page can also queue a custom character request, follow an existing actor, stop following and
stop the worker. It never accepts keys in browser fields or starts private
reflection processing. Credentials must already be supplied to the launcher
process by the host. No command-line author/enrollment steps are required once
that environment is configured.

Read-only page entry never starts a worker or model. Follow is for existing
records; the initialize-all path enrolls future turns automatically.
Initial requests are idempotent for the same actor/purpose. If no allowed public
evidence exists, authoring cannot invent it. Other worlds and remote/friend
servers cannot be controlled from this local-owner page. Closing/disconnecting
the hosting session stops its existing worker and preserves queues.

## What actually starts the characters

A server starts no model by itself. Original actors have no extra behavior until
an approved authored record exists. There is no default fake arc or bootstrap
victory. The explicit initialize-all request supports first identity-based goals
and greetings only. Other canonical actions need real allowed public history.
Private campaign observations alone do not qualify; sharing remains the players'
choice. Advanced hosts can also use the existing typed `canonical_actions` path.

Check the host author installation without a model call or queue write:

    python3 -m world.runtime_gm check-author

The legacy Codex adapter requires `codex-cli 0.156.1` and its bundled Luna catalogue.
Direct OpenAI Responses and Anthropic Messages are now separate explicit backend
choices and do not invoke Codex. See [author backends](AUTHOR_BACKENDS.md).
It uses the CLI's existing ordinary login; this check does not inspect credentials
or prove provider login/network access. Do not loosen the version/tool isolation
gate merely to get a green check. A different CLI needs separate security review.

Using the existing running world's transport socket (the client resolves the
separate host-only admin socket internally) and a dedicated author state dir,
the host can queue one explicit initialization request (replace placeholders):

    python3 -m world.runtime_gm submit --state-dir AUTHOR_STATE --player HOST \
      --intent "Consider one original cast member using actual inspected public history. Use canonical_actions, preserve original scripts, and invent no outcomes."
    python3 -m world.runtime_gm run --state-dir AUTHOR_STATE --socket TRANSPORT_SOCKET \
      --model openai-codex/gpt-6-luna --once

This is a real model/deployment request, not a dry run. If evidence is insufficient,
resolve that normally; do not manufacture history. After a canonical actor exists,
explicitly enroll its future public-history reactions:

    python3 -m world.runtime_gm follow-character --state-dir AUTHOR_STATE \
      --socket TRANSPORT_SOCKET --id canon_rydel \
      --purpose "Develop Rydel from actual public events and supported actions, preserving his bike service and individual trainers."
    python3 -m world.runtime_gm run --state-dir AUTHOR_STATE --socket TRANSPORT_SOCKET \
      --model openai-codex/gpt-6-luna

Use the corresponding existing `canon_wally`, `canon_briney`, or `canon_steven`
record for other actors. Enrollment never creates them. Host-selected purposes,
actual evidence, supported actions, bounded intentions and optional quiet-world
routines govern behavior. No physical travel, battle or training is inferred
from elapsed time. `status` inspects the queue; `unfollow-character` withdraws an
actor. Interrupt the run process normally to stop model operation.

Both public run startup and private-worker CLI startup check selected local
prerequisites BEFORE opening/claiming work. A missing/incompatible CLI therefore
cannot consume queued turns or private response grants merely because startup
was attempted. The per-call adapter still rechecks its version and isolation.

## Connected player entry points

- Talk to original Rydel at the Bike Shop, Wally at the reviewed Wanda house or
  completed Victory Road continuations, Briney at Route104 house, or Steven at
  his reviewed post-Dive house state. Original progression/services still decide
  eligibility. There are no duplicate actors.
- SELECT opens an authored shared speaker/listener question. START opens the
  actor's actual local owned project. A chooses; B resumes the original script.
  Actors' actual project commitments can change the choices on later visits.
- Existing native scene/partner invitations remain optional. Project conditions
  can control availability, but cannot substitute for player participation.
- Registered Wally/Steven can use actual PokéNav calls; no invented contacts.
- Private memory/reflection is a separate opt-in, never shared-author input.
  The private worker is separately and explicitly started, for example:

    python3 -m world.private_cast_worker --socket TRANSPORT_SOCKET \
      --model openai-codex/gpt-6-luna --watch --max-jobs 8

See the connected journey and feature documents for exact commands and limits.
These are reusable affordances, not a promise that every author will select them.

## Verified versus outstanding

Current environment: Codex reports `0.167.0-alpha.4`, not the reviewed version;
SDL2 development metadata is missing. The direct API backends avoid that CLI dependency, but were not called live.
Consequently no live-model author run or
full linked native build is claimed here. Do not change the gate to hide this.

Component suites exercise real authority/compiler/queue paths and compiled
production native handlers with explicit engine/UI doubles. Maya still needs
full engine build, two-to-four-client rendering/input, original story/services,
party/save/reload, disconnect/recovery, live author quality/cost and privacy QA.
The manifest explicitly marks linked-native and live-author validation false.

### Start the original cast together

After choosing a provider/model and authorizing public authoring, choose
**Initialize and follow original cast**, then start the world author. This
subscribes Rydel, Wally, Mr. Briney and Steven together, retaining existing
records and event cursors. No hand-written starter scripts or purposes needed.

For each missing actor the authority records the actual host commissioning
request once. This is explicitly setup evidence, not an in-world experience.
It can justify only that actor's first identity-based goal and supplemental
greeting: no relationship, service, offer, project, team, achievement or later
growth may cite commissioning. The configured agent chooses the content from
source-grounded identities through normal typed compilation and authority
admission; there is no fixed arc or fake opening adventure. Until it succeeds,
ordinary Emerald dialogue continues. Talk again to the original actor at its
existing safe story point after authoring completes to see the new greeting.

Subsequent real public events trigger ordinary bounded character decisions.
For example an opted-in public Mauville Gym expedition result may inform Rydel
and Wally independently, without implying a victory or their participation.
No campaign sharing, guild chronicle or private-memory option is enabled by
cast setup. Private conversations and per-save progress are not published.

Enrollment does not start the model automatically or retry failed attempts.
The durable commissioning receipt and queue cursor survive restart, and
repeated clicks do not duplicate work. Stop following actors individually or
stop the author. Failed initialization stays failed for that request; distinct
future relevant evidence can still prompt a fresh initial decision. Profiles
are background, never outcome evidence. The deterministic fixtures exercise
real authority admission; live model and rendered native QA remain separate.
