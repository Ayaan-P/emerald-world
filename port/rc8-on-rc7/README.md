# RC8 on Expansion RC7: draft preparation

This is an independent integration branch. Its parent history merges RC8 into RC7 and carries RC7's build-20 sender-count checkpoint. It does not modify Maya's branch or assert that shared co-op is fixed.

The engine submodule points to RC7's local-only engine commit `fb9e7bde1a6895b4a1a9dfe9ff47f94a7e67e212`, which cannot be fetched from the configured upstream. Reconstruct RC7 using the three source patches in `docs/attempt-handoffs/rc7/CURRENT.md`, verifying the resulting tree is `289ad25553d2de1a8e6e57cb4cb110ee5841e108`. Then apply `engine.patch` in that engine tree. The patch carries the RC8 XL generated-world, shared-terrain, map loader and durable offline-story code into the Expansion engine and adjusts the native options.

RC7's normal build wrapper verifies commit ancestry: a source-only reconstructed tree does not reproduce those commit objects, and no ancestry check has been bypassed. A full native build, release, fresh-clone build, multiplayer and actual game replay have not been verified. Build 20 co-op itself was pending when its handoff was written. Use disposable saves only. The larger map buffer may require an EWRAM capacity change; that cannot be judged without the full link and mandatory checks. Later RC7 updates need to be carried forward explicitly.

Focused checks: `EW_RC7_ENGINE=/path/to/reconstructed-engine PYTHONPATH=.:test/world python3 -m unittest test_rc7_xl_port test_rc7_xl_durable -q`. The engine patch includes a standalone options parser test under `tests/rc8`. The focused tests are not a substitute for building or playing the combined game.
