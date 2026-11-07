# World rules (draft)

Each world owns a versioned, validated rules document persisted in its authority database. Vanilla is the default. The first implemented rule is `wild_shuffle`, with an enable switch and seed 1–20; its existing permutation covers the original 386 National Dex species. Newer species remain unchanged. Rule data never edits a trainer's save and is not executable code.

An owner-authorized agent or host can inspect the rules with `python -m world.rules_control --admin-socket PATH status`, then replace them using `python -m world.rules_control --admin-socket PATH set --revision N --wild-shuffle on --seed 7`. A stale revision is rejected. For this first version all players must leave before changes, so nobody silently starts an encounter using different rules. The admin endpoint is the existing host-only authority, not a public player command.

Compatible clients negotiate `RULES1` and receive the same setting after authentication. While connected, WORLD > Wild shuffle shows the world's setting and cannot override it; a player's previous local setting is restored on disconnect. A non-default world rejects older clients that cannot follow the rule. Compatible clients fall back to their earlier behavior when connecting to an older server. This is compatibility enforcement, not anti-cheat protection against modified clients.

This is experimental source integration. No combined native build, GUI playthrough, real multiplayer session, or full co-op regression has been run. The current rule does not cover scripted, generated-area, Frontier, outbreak or special encounters; rules are not synchronized during a mid-battle disconnect. Use disposable saves. The standard RC7 integration and newer engine changes still need reconciliation before release.
