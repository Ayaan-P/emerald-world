# Persistent-character rendezvous

`world.rendezvous(target=character_id)` is a discovered capability for generated
world-owned characters. It uses the public authority registry, not claimed sight,
private player tracking, remote dialogue or fictional travel.

The actor chooses whom to seek. Authority computes paths to a free adjacent tile
and traverses existing directed cave links when necessary. After each real leg it
reads the recipient's current location again. It never moves or freezes the
recipient, accepts a meeting on their behalf, or starts a player conversation.
A successful result means both current authority objects are idle and adjacent;
it returns the recipient's current version for a subsequent `world.address`,
observation handoff or voluntary cooperation action. Actual dialogue remains an
independent choice by the recipient's existing model-driven lifecycle.

Navigation and cave transfers use the existing staged movement executor, occupancy
checks, immutable map identities and persistent receipts. Observers receive the
same existing character objects/walk rows, not duplicate NPCs. Restart resumes
pending legs without claiming an arrival. A changed or missing actor/link and an
unreachable destination fail truthfully. Active player battles pause new legs.
Pursuit is bounded to sixteen completed legs per action; an agent can inspect the
blocked result and choose a different plan. This is not a lifetime actor limit.

Scope: same supported generated maps and already-installed cave links. No original
Hoenn/canonical actor relocation, outdoor REGION1 admission, player warp, combat,
forced meeting or promise of rendered synchronization. Finishing a route does not
prove an NPC agreed, learned something, or changed their relationship.

This app-only draft uses the existing #339 native pin, with no new native code and
no dependency on blocked evolution. It is based on our #339 stack, not released
RC12 (app f484577b606348d07337387f14f75ab8cf4970b6, engine
f7a813317d1b9fec803b48b682f5d74245c79037). Maya owns release reconciliation and rendered
QA; her integration branch is untouched.
