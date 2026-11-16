# Agent-chosen optional trainer lineups

Stack on PR311; native remains PR32. No replacement of canonical story teams,
player parties/saves, battle mechanics, or native consent UI.

`world.prepare_challenge(lineup,text)` lets a world-owned trainer select one to
six owned individual IDs, in order, and a short literal invitation. The generic
catalog exposes `companion_rosters`: stable identities, species, authored and
actual trained levels, whether currently selected, and ownership/personality.
The tool cannot mint a Pokémon, edit levels, claim capture or grant experience.

Lineups pass through the existing typed character compiler and normal staging.
Only admitted state yields an optional-challenge-prepared receipt. Players then
approach and explicitly choose the ordinary native battle; the capability itself
never starts one. Pending player descriptors remain frozen if the NPC changes
its next lineup. Reconciled full Pokémon state is supplied by CHARPK2 unchanged.
Client-reported outcomes remain informational and cannot train NPCs.

The durable roster retains identified companions removed from the current team,
so agents can bench and later restore them without replacing identity. Existing
current teams are available immediately; removed companions from before this
roster feature cannot be restored through it unless their authored level is
actually retained. No historical values are guessed.

New `world.populate` NPC teams now receive stable per-slot individual IDs when
none were supplied. These are authored initial Pokémon, not captures or earned
growth. Explicit complete individual IDs remain supported. Compatible CHARPK1
clients are required; no silent downgrade to anonymous Pokémon. Existing old
anonymous NPC records are not silently changed or assigned past experiences.

Tests cover actual staged lineup admission, authenticated optional challenge,
frozen pending descriptors, bench/restore identities, unknown ownership refusal,
and preserved reconciled full state through the paired native component. Native
Pokémon APIs are fixtures in that component test, not a linked/rendered battle.
No live model calls. Maya owns integration and gameplay QA.
