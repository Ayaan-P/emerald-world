# Agent-directed optional Singles and Doubles

An existing generated trainer with individually owned companions can use
`world.set_battle_format(format="doubles")` in its ordinary model-authored plan.
The choice can follow actual history and previous tool outcomes; there is no
prewritten tournament, named-character arc or invented result. The current
format and revision are included in capability discovery. `singles` restores the
normal optional challenge.

A visitor approaches the same NPC and sees **A Singles** or **A Doubles** in the
existing field choice. The authority freezes format revision with the team;
changing the offer while a player is considering it invalidates that choice.
Doubles requires two individually owned NPC team members and native checks for
two usable player Pokemon. Full-state NPC lineups also need two conscious
non-egg members. Ordinary native double-battle rules and AI run, without a
server-selected player party or raw flag injection. This is one player's double
battle against an NPC, not a two-player co-op multi battle.

CHARFORM1 negotiates CHARACTER_FORMAT snapshot rows, exact-revision challenge
requests and CHARACTER_BATTLE_V4 responses. Persistent personality/owner and
optional full-state payloads remain intact. Legacy clients may still use normal
Singles, but cannot silently turn a configured Doubles challenge into Singles.
Native launch retains existing activity, script, link/co-op and field-safety
checks. Normal campaign trainers and saved story flags are unchanged. Native
battle effects remain normal game effects; private client result reports are
not trusted training or victory evidence.

## Current validation / publication

Native draft #41 publishes e0e071078bd4f3fde671818dc87eae9bde745170; this app
candidate pins that exact head in the gitlink and builder. It is stacked on
published app #339, including the independent later features. The earlier denied
upload succeeded once the user specifically approved that payload/destination.

This is our draft stack, not Maya's released RC12 baseline. Released app
f484577b606348d07337387f14f75ab8cf4970b6 and native
f7a813317d1b9fec803b48b682f5d74245c79037 contain separate integration fixes that
Maya must retain when integrating. Nothing here overwrites or claims to include
those release fixes. The new evolution investigation is not part of this pair.

Tests execute actual authority plans, snapshot and opponent wire through the
actual native parser/menu/start function, plus native opponent preparation. They
cover restart, frozen consent, old clients, insufficient/fainted/egg party cases,
and unchanged player-party bytes at launch. Platform calls and the subsequent
battle loop are fixtures. Full linked/rendered double battle, save/return and
co-op regression QA remain Maya's responsibility; no live model was called.
