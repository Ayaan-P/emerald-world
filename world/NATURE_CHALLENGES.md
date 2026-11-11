# Experimental nature-driven generated NPC singles

Independent child of native #79 (`d1075e135c443e4e2cf1940fffa9657c3ed371ec`), not Maya #72 or released RC12. Disabled by default. Build an isolated QA copy with `NATIVE_EXTRA_CPPFLAGS=-DWORLD_NATURE_CHALLENGES=1`; do not promote to normal distribution before linked gameplay QA.

In that build, the local private command `/nature-battles on` explicitly enables the mode for subsequent solo generated-NPC single battles in this process. `/nature-battles off` restores ordinary move choice for future challenges. Settings cannot change during an encounter. The choice is session-local, not saved or sent to other players. No server or agent can silently enable it. The ordinary optional challenge prompt still controls whether a battle starts.

When Fight is selected, both sides use the existing `ChooseMoveAndTargetInBattlePalace` implementation. Actual natures, move lists, PP, limitations and HP-dependent selection apply. Pokémon may fail to act under the existing Palace rules. This is not a new scoring AI, guaranteed move selection, growth or mastery. Party switching and other ordinary battle actions remain available; this is not a recreation of the full Palace ruleset.

A separate `IsNatureMoveSelection` predicate enables only selection-related controllers, AI preparation, limitation handling and nature HP/flavor behavior. It does not set BATTLE_TYPE_PALACE or run facility initialization, prizes, streaks or facility party materialization. Canonical and wild battles remain ordinary. Doubles, co-op, link, multi and recorded playback exclude this mode. Existing Palace battles retain their original predicate behavior.

The selection preference is frozen in WorldCharacter_Prepare; cooperation disables it. Recording initialization latches a rejection for the entire record buffer. Saving that record returns false before allocation or writing, preserving a previous stored recording. The latch survives encounter finish and resets on the next recording/playback initialization. No new replay format is claimed.

Four component tests pass, including compiling actual guard/command/record-init functions with feature off and on, plus source assertions for selection hooks and pre-write recording rejection. Tests do not execute the complete selector or a rendered battle. Full native build, PP/HP/Struggle/gimmick combinations, defeat/forfeit callbacks, linked gameplay and platform QA remain required. No live providers or player saves were used.

App child of #428, paired with native #80. Build through `scripts/build_expansion.py --development --experimental-nature-challenges` on the verified native pin. Normal build paths pass WORLD_NATURE_CHALLENGES=0. Native map/species catalog content is unchanged; resident/encounter metadata pins advance with the source. This draft is not Maya's reconciled #410/#72.
