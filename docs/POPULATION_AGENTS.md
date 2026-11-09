# Independent agents for newly created NPCs

Stack on PR309; native PR32 remains unchanged. This completes the optional path
from `world.populate` to an independently authored character, rather than claiming
that a durable record alone is an agent.

The local host may enable **automatic new-character agents** in the existing
Living cast panel. This does not start a provider. It authorizes the configured
Claude/OpenAI worker to process future creation receipts from followed actors.
Existing characters are not silently backfilled, and props never become agents.

After a successful admitted population receipt, the worker enrolls the actual
active child record and queues its first typed decision. Its own goals, true
location, capability catalog and exact creation evidence are supplied. The child
may choose an independent plan or wait; it does not inherit its creator's plan.
Subsequent actual tool results, encounters and supported events feed the existing
reaction loop. No new model process, hard-coded scenario or invented experience.

Automatic lifecycle is bounded to eight author attempts per NPC and the existing
eight-followed-actor ceiling. Reaching the limit pauses follow-up rather than
silently incurring unbounded provider charges. A failed attempt counts; it is not
retried. Capacity-full creations are not enrolled retrospectively. Existing world
record and population admission limits remain unchanged.

Stopping automatic agents removes managed subscriptions and interrupts queued
turns. Individual unfollow and retirement also stop future turns. Already running
provider calls and committed world plans cannot be undone by this control.
An explicit host world goal takes over a character under the normal goal policy.
The host can inspect active/stopped/budget-reached lifecycle statuses. Settings,
creation identities and attempt accounting survive worker restart.

Tests use actual population staging/admission, queue and authority observation.
Both official provider adapters receive fake responses that author the child's
own observation plan, execute it against real local geometry, consume its actual
receipt and reconsider independently. Restart, off-by-default, props, disable,
UI authorization and bounded attempts are tested. No live API or rendered-game
claim. Full worker sandbox/linked-native QA remains separate and belongs to Maya.
