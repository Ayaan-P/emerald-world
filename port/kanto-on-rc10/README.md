# Kanto engine pinned on RC10

App base: `3d336831f06672c93ea3e4402f95aba4dd0b55b6` (`main`, RC10).
Native repository: <https://github.com/Ayaan-P/pokeemerald-expansion-native>.
Native branch: `dot/kanto-on-rc10`.
Native commit: `e2aa70213d1176763b154bb338da18d97afa595b`.
Native tree: `8eedfe361c12dc2af6ca2b98911b17658bfb118b`.
Native parent: `c8feb78cfb7bdd82c19406eabe0f36716ea87f16`.

The submodule and `scripts/build_expansion.py` use that published commit. Fetch
the real repository history; no RC7 reconstruction or old RC9 patch is needed.
`source-manifest.json` records the 44 native files changed from RC10 and their
SHA-256 hashes. The native branch is published; it is not merged or deployed.

The current app cohort includes the opaque save-copy bounds from app PR #255.
These preserve the complete native save and optional regional extension. The
native loader still validates version, length, CRC and ABI.

With the existing native build prerequisites available, use:

```
python3 scripts/build_expansion.py --development --regional-state --kanto-content
```

Optional `--sysroot` and `--multilib-sysroot` select existing SDK inputs. No
packages are installed by the wrapper. Ancestry, isolation, data-relocation,
data-layout and battle-script operand checks remain mandatory. Species metadata
is exported only after a successful native build creates its required headers.
Both regional switches remain off by default.

This is an integration draft, not a playable multiregion release. See
`docs/KANTO_MULTIREGION_DRAFT.md` for exact tests and remaining gaps. In the current
environment the guarded full build stops because Bubblewrap cannot create its
network-namespace setup socket. Do not disable isolation or checks to continue.
