# Documentation map

## Current source and player guidance

- [Project README](../README.md): current mainline, published-download distinction, quick start and implemented features versus acceptance.
- [RC12 candidate and private source handoff](RC12_BUILD_RELEASE.md): delivered RC11 baseline, frozen build cohort, private-engine access and remaining release gates.
- [RC9 scope](RELEASE_RC9.md): the older publicly downloadable Expansion package.
- [React launcher](../launcher-web/README.md): Local/Hosted sessions, generated caves, private saves and lifecycle controls.
- [RC6 scope](RELEASE_RC6.md): earlier inhabited-area and interactive-adventure boundaries.
- [RC5 release notes](RELEASE_RC5.md): scope of the published `v0.2.0-rc.5` player package.
- [Linux packaging and installation](linux-packaging.md): player archive and user-local installation.
- [Native source build](../INSTALL_PC.md): Linux, Windows and macOS toolchains and pinned local build inputs. A platform target is not multiplayer acceptance on that platform.
- [Integration status](INTEGRATION_STATUS.md): accepted stacks, original PR reconciliation and unintegrated work.
- [Development rules](../CLAUDE.md): portable guards, pointer widths, save conversion, deterministic frames and development conventions.
- [Product direction](PRODUCT_DIRECTION.md): longer-term goals. It describes direction, not a complete shipped-feature list.

## Runtime and repository map

- `engines/expansion-native/`: pinned private Expansion engine source, game data and platform runtime. The app feature cohort is selected by `engines/expansion.mk`.
- Root `src/`, `include/`, `data/` and `src/platform/`: historical vanilla engine and its native world implementation, not the current Expansion release build.
- `world/`: Python authority, session lifecycle, profiles, generated-content formats, owner controls and launcher HTTP bridge.
- `launcher-web/src/`: primary React launcher. The source Tk launcher remains a fallback/operator interface.
- `scripts/`: asset restoration, clients, packaging and installation.
- `test/world/`: protocol and production-component tests, including C compilation fixtures.
- `test/headless/`: native game driver, smoke scenarios and focused playthroughs. [Driver documentation](../test/headless/README.md).
- `deploy/`: persistent dedicated service operation. [Deployment guide](../deploy/README.md).
- `.github/workflows/`: actual CI commands and feature-gate builds. [Main baseline](../.github/workflows/main-baseline.yml). Full-platform legacy checks are manual-only in [build.yml](../.github/workflows/build.yml).

Native build outputs, runtime profiles and dependencies are not repository source. A developer's local `build/` evidence may not exist in another clone. Git history, committed tests and linked PRs remain the portable record.

## Focused implementation references

These documents describe particular interfaces. Their draft titles do not mean their code still needs to be merged.

- [Interactive event graphs](AGENT_AUTHORED_EVENTS_DRAFT.md).
- [Live owner event controls and client outcomes](LIVE_AGENT_EVENTS_DRAFT.md).
- [Generated-area archive](GENERATED_AREA_ARCHIVE_DRAFT.md).
- [Generated outdoor casts](GENERATED_WILDS_CAST_DRAFT.md) and [shared casts](SHARED_WILDS_CAST_DRAFT.md).
- [Shared generated caves](SHARED_GENERATED_CAVE_DRAFT.md).
- [Owner-funded medicine](COOP_BATTLE_POTIONS.md), [reserve medicine](COOP_BATTLE_MEDICINE_RESERVES.md) and [six-Pokémon switching](COOP_FULL_SIX_DRAFT.md). These describe implemented components, not completed combined-player acceptance.

Other `*_DRAFT.md` files remain as design and narrow experimental evidence for their individual stacks. Current release notes take precedence for player availability. Current code and PR heads establish whether a change remains unintegrated.

## Historical evidence

- [Historical co-op evidence](COOP_STATUS.md): dated local/WAN acceptance and limits. Its old baseline hashes do not identify current main.
- [Earlier player release scope](PLAYER_RELEASE_SCOPE.md): the pre-RC5 co-op contract. Its three-combat-Pokémon limit is not the current integrated roster implementation.
- [RC5 local candidate evidence](RC5_LOCAL_CANDIDATE.md): development record, distinct from the published RC5 notes.
- [Pre-RC6 README](archive/README_PRE_RC6.md): preserved old tkinter steps, roster/bag/capacity text and earlier verification. Not current player instructions.

No historical documents, feature branches, release tags or worktrees were deleted in this cleanup. Retaining evidence does not imply an abandoned experiment is supported or every previously observed result has been reproduced on the current revision.
