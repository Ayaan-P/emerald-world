# RC8 on Expansion RC7: draft preparation

This is an independent integration branch. Its parent history merges RC8 into RC7 and carries RC7's build-22 sender-count checkpoint. It does not modify Maya's branch or assert that shared co-op is fixed.

The engine submodule points to RC7's local-only engine commit `dd4cbc90f985735097d21dc202bc4cc3fe9b0f46`, which cannot be fetched from the configured upstream. Reconstruct RC7 using the three source patches in `docs/attempt-handoffs/rc7/CURRENT.md`, verifying the resulting tree is `0026146184b0eb0fe003742f6d4095aff3dc4fbc`. Then apply `engine.patch` in that engine tree. The patch carries the RC8 XL generated-world, shared-terrain, map loader and durable offline-story code into the Expansion engine and adjusts the native options.

RC7's normal build wrapper verifies commit ancestry: a source-only reconstructed tree does not reproduce those commit objects, and no ancestry check has been bypassed. A full native build, release, fresh-clone build, multiplayer and actual game replay have not been verified. Build 20 co-op itself was pending when its handoff was written. Use disposable saves only. The larger map buffer may require an EWRAM capacity change; that cannot be judged without the full link and mandatory checks. Later RC7 updates need to be carried forward explicitly.

Focused checks: `EW_RC7_ENGINE=/path/to/reconstructed-engine PYTHONPATH=.:test/world python3 -m unittest test_rc7_xl_port test_rc7_xl_durable test_rc7_shared_xl test_rc7_large_agent_terrain test_rc7_shared_agent_geometry test_rc7_generated_runtime -q`. The engine patch includes a standalone options parser test under `tests/rc8`. The focused tests are not a substitute for building or playing the combined game.

Guild server functions and native guild menu/chat gate are included. The opt-in wild shuffle is carried to Expansion ordinary encounter and fishing paths, using the original stable 1–386 National Dex permutation. Species beyond 386 remain unchanged. Both are unverified in a combined game, co-op and real server sessions. Trading remains excluded.
