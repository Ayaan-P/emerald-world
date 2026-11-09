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

## What actually starts the characters

A server starts no model by itself. Original actors have no extra behavior until
an approved authored record exists. There is no default fake arc or bootstrap
victory. Initial canonical actions need real allowed public history. Private
campaign observations alone do not qualify; use normal explicit sharing controls
only when the players choose to share. The first record can be authored through
the existing host GM submit/author/deploy path using `canonical_actions`.

Check the host author installation without a model call or queue write:

    python3 -m world.runtime_gm check-author

The legacy Codex adapter requires `codex-cli 0.156.1` and its bundled Luna catalogue.
Direct OpenAI Responses and Anthropic Messages are now separate explicit backend
choices and do not invoke Codex. See [author backends](AUTHOR_BACKENDS.md).
It uses the CLI's existing ordinary login; this check does not inspect credentials
or prove provider login/network access. Do not loosen the version/tool isolation
gate merely to get a green check. A different CLI needs separate security review.

Using the existing running world's admin socket and a dedicated author state dir,
the host can queue one explicit initialization request (replace placeholders):

    python3 -m world.runtime_gm submit --state-dir AUTHOR_STATE --player HOST \
      --intent "Consider one original cast member using actual inspected public history. Use canonical_actions, preserve original scripts, and invent no outcomes."
    python3 -m world.runtime_gm run --state-dir AUTHOR_STATE --socket ADMIN_SOCKET \
      --model openai-codex/gpt-6-luna --once

This is a real model/deployment request, not a dry run. If evidence is insufficient,
resolve that normally; do not manufacture history. After a canonical actor exists,
explicitly enroll its future public-history reactions:

    python3 -m world.runtime_gm follow-character --state-dir AUTHOR_STATE \
      --socket ADMIN_SOCKET --id canon_rydel \
      --purpose "Develop Rydel from actual public events and supported actions, preserving his bike service and individual trainers."
    python3 -m world.runtime_gm run --state-dir AUTHOR_STATE --socket ADMIN_SOCKET \
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

    python3 -m world.private_cast_worker --socket ADMIN_SOCKET \
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
