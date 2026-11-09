# Reusable optional NPC move tutoring

`world.offer_tutoring(move)` lets a world-owned recurring character open, change
or close a training opportunity. Discovery lists the ten existing Emerald tutor
moves and their exact engine identifiers. Move 0 closes the offer. An agent may
choose based on committed history and its own plan; no named character arc or
claim of teaching competence is imposed.

A CHARTUTOR1 native client shows **L Tutor** after the usual greeting. It names
the actual move and asks whether to choose a Pokémon. A opens Expansion's
existing party tutor menu; B declines. The player selects their own Pokémon,
and the engine enforces egg/species eligibility, already-known moves and its
normal learn/replace/cancel flow. The agent cannot supply a party slot, replacement
slot, raw Pokémon data or arbitrary move IDs. No forced interruption occurs.

These are explicitly **free, repeatable optional opportunities**, not the original
one-time tutors. Their original scripts and completion flags are untouched.
Only the normal player-chosen native learning flow changes that player's Pokémon.
No server bag, money, XP, team or save writes are performed. A service offer is
not proof that anyone learned a move; there is no purchase/learning-report packet
or automatic relationship reward.

The native adapter freezes and rechecks the offered move/revision before opening,
uses the same stationary exact-character/region interaction guard as other services,
and restores temporary script variables on return. It returns to the field through
an explicit callback, never resuming an unrelated vanilla script. Once native
learning begins, disconnect does not retarget the operation or undo the player's
own choice. Old clients omit the offer; new clients peel this capability first
when connecting to older servers.

Tests execute a real author plan and persistent offer, then feed the actual
authority snapshot to compiled C parser/menu/party-entry/callback fixtures. These
do not replace linked QA. Maya must verify actual eligible/ineligible/egg choices,
four-move replacement and cancellation, no item consumption, save/reload,
disconnect and shared-world coexistence. No live model or rendered learning
playtest is claimed.

Paired native draft #40: 8e409094ccd226a66c9cf8bfef2f545f2be52c28.
