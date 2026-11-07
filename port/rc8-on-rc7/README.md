# RC8 on Expansion RC7: draft preparation

This independent integration branch combines RC8 with RC7 through build 26. Maya's build-26 evidence records a two-player grass battle, private EXP and cold-loaded separate saves in RC7 alone. This branch has not repeated that journey with the combined changes.

The engine submodule points to RC7's local-only engine commit `1d82672e93db02a28a1deea281c5f694f52a5e9e`, which cannot be fetched from the configured upstream. Reconstruct the RC7 source using the three patches in `docs/attempt-handoffs/rc7/CURRENT.md`; the documented resulting tree is `e33f8cae5e4c6bb76d0e640b5dac51d42a4ddc61`. Apply `engine.patch` to that tree. The normal build wrapper checks commit ancestry, which source reconstruction does not recreate; its check has not been bypassed.

RC7's Expansion-native generated caves use versions 10 and 11. RC8's XL wilds now negotiate `CAVE16` and use internal wire version 16, preserving their existing `EWGMAP0A` file format. Older clients do not receive an incompatible XL map. Focused tests cover XL and Expansion cave parsing and capability separation without opening sockets.

A full native build, fresh-clone build, combined multiplayer and actual combined game replay have not been verified. Use disposable saves only. The larger map buffer may require an EWRAM capacity change; that cannot be judged without the full link and mandatory checks.

Focused checks: `EW_RC7_ENGINE=/path/to/reconstructed-engine PYTHONPATH=.:test/world python3 -m unittest test_rc7_xl_port test_rc7_xl_durable test_rc7_shared_xl test_rc7_large_agent_terrain test_rc7_shared_agent_geometry test_rc7_generated_runtime -q`. The engine patch includes a standalone options parser test under `tests/rc8`. These tests are not a substitute for building or playing the combined game.

Guild server functions and native guild menu/chat gate are included. The opt-in wild shuffle is carried to Expansion ordinary encounter and fishing paths, using the original stable 1–386 National Dex permutation. Species beyond 386 remain unchanged. Both are unverified in a combined game, co-op and real server sessions. Trading remains excluded.
