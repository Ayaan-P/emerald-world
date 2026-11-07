# RC7 full-engine replacement attempt: failed/WIP checkpoint

> Historical initial checkpoint only. This file's failed-build/runtime statements
> are not the current RC7 status. See [CURRENT.md](CURRENT.md) for the latest
> source delta/reconstruction, and [the workboard](../../RC7_WORKBOARD.md) for
> current gameplay evidence and ownership.

Not a working release. The 17 selected RC7 world modules passed a syntax-only check against Expansion headers. The native extra-object tile-bank pixel fixture passed. Neither is multiplayer gameplay verification. No completed two-client Expansion battle/trade/co-op test exists.

The native engine source was checkpointed locally as e406cf82922e9c3a5bfee746f9a97f67f3916a4c. Its last verified standalone foundation was c22527265e72236fb269937d9705bafa49cc02cc, incorporating Expansion 1.17.2 (79dd436920845ebc145577649de624f65298c209). The later world integration is incomplete.

The latest complete build log is evidence/rc7-world-port-09.log. It failed the mandatory data-relocation checker with 21 reported mismatches between the changed 64-bit repel scripts and stale/differently configured four-byte reference objects. Exporting NATIVE_EXTRA_CPPFLAGS was attempted but did not clear the existing reference stamp. This is an observed failure plus an unverified diagnosis, not a proven fix. No checker was disabled. More engine-facing battle/controller, private reward, trade/recovery and host UI/control hooks remain to be checked or completed. Launcher changes also remain unverified.

## Source handoff without distributing upstream ROM/executable files

The parent gitlink records the LOCAL native WIP commit. That object is deliberately not pushed as a full upstream-history bundle: the upstream repository contains tracked .gba/.exe files. Do not expect `git submodule update` to fetch the local WIP object from upstream.

Both source deltas are preserved here as binary-capable Git patches (source graphics/map assets included, ROM/save/executable paths excluded):

1. Clone the trusted public native repository separately and check out bb3fd057061cdd7e6a9e79b76abb41924ee44ecc.
2. Apply native-foundation.patch with `git apply --binary`.
3. Apply native-world-wip.patch with `git apply --binary`.
4. provenance.json identifies all exact source revisions and hashes of protected upstream input files, which are not distributed here. Required local SDL/multilib build inputs are described by evidence/expansion-input-reuse.json and scripts/build_expansion.py. No dependencies are bundled or installed.

The patch reconstruction yields the source changes, not the same Git commit identity or a verified runnable build. scripts/build_expansion.py still checks ancestry against the original foundation, so a reconstructed fresh history needs deliberate provenance handling before using that wrapper; do not silently bypass it.

Evidence contains the build logs, read-only compatibility probe, research source ledger and the small migration scripts from the ignored build directory. Executables, saves, installed dependencies and raw runtime/profile data are excluded. The obsolete engines/expansion_presence.c file is retained as historical scaffolding but is no longer linked by engines/expansion.mk.
