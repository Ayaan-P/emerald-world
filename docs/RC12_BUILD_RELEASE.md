# RC12 candidate build and private source handoff

## Release status

RC11 is the delivered release baseline. This branch contains RC12 candidate source, not a published RC12 package. The [RC11 decision](releases/RC11-RELEASE-DECISION.json) records the existing build and its limits. Public GitHub downloads remain RC9. Do not equate a candidate source commit, a passing standalone engine replay or a local launcher build with an installed release or a hosted-service deployment.

The release integrator owns the final paired app/engine pin and version. This change does not select those RC12 values. The current `scripts/build_expansion.py:PIN` and committed `engines/expansion-native` gitlink must agree. The builder rejects a mismatched gitlink, a different engine HEAD or a dirty engine before building a release.

## Private engine access is a prerequisite

The app repository is public. `Ayaan-P/pokeemerald-expansion-native` is private. The app workflow's default `GITHUB_TOKEN` cannot read that other repository, even with `contents: read` in the app workflow. A public unauthenticated clone cannot reproduce the full game source.

The approved access input is the repository Actions secret `EW_ENGINE_READ_KEY`, backed by a dedicated read-only SSH deploy key on the engine repository. The main baseline workflow checks out the public app normally, without submodules or persisted credentials. It validates the committed engine gitlink as a 40-hex commit, then checks out that exact revision using the deploy key only for the private engine, with strict SSH host-key checking and without persisted credentials. It does not substitute engine `main`, remove tests, change visibility or fall back to an unauthenticated fetch. A missing secret fails with an actionable error. Untrusted fork pull requests do not receive this secret and therefore cannot pass the private-source gate without a separately reviewed trusted run. Do not change this workflow to `pull_request_target` to expose the credential.

The maintainer approved and registered engine deploy key `169206706` and configured the encrypted app Actions secret `EW_ENGINE_READ_KEY`. Secret metadata and a real Git read using that key with strict GitHub host-key verification were verified separately. No personal access token was copied and repository visibility did not change. This source adaptation reads no secret values. The release integrator owns the final paired pin push order and hosted workflow verification. No green hosted CI run is claimed here.

For local source builds, use the maintainer's approved existing Git access. Do not paste a token into commands, repository files or logs:

```sh
git clone https://github.com/Ayaan-P/emerald-world.git
cd emerald-world
git submodule sync -- engines/expansion-native
git submodule update --init engines/expansion-native
python3 scripts/build_expansion.py --check
python3 scripts/build_expansion.py --jobs 2
```

If the private repository returns `Repository not found`, resolve access with the maintainer. Do not reset to an upstream donor or use `--development` to get past a release pin failure.

## Frozen build cohort

The ordinary builder, without `--development`, selects the existing combined release configuration:

| Input | Value |
| --- | --- |
| `MAP_VERSION` | `combined` |
| `EW_REGION_STATE` | `1` |
| `EW_KANTO_CONTENT` | `1` |
| `GENERATED_WORLD_REGIONS` | `0` |
| Native identity | pinned engine abbreviation plus the existing `rc11.3` suffix |

`ReleaseConfig` in the builder is frozen. `engines/expansion.mk` defaults to the same combined cohort and exports the full app feature flags to recursive pointer4 reference builds. The builder records its build inputs and wrapper content in `build/native64/ew-release-cohort.txt`. It discards stale native objects when these inputs change or are unknown. Pointer4 references are regenerated for each build. The mandatory data relocation, layout, battle-script operand and trainerbattle serialization checks remain in the native build graph.

`--development` is for intentional local engine integration only. It permits a descendant/dirty engine and allows the explicit regional/Kanto development switches. It is not required for the normal release cohort and is not release verification. Existing evidence showing `--development --regional-state --kanto-content` describes the old build invocation, not the current release command.

Use Python 3.11+, GNU make 4.3+ (grouped map-generation outputs), a C/C++ toolchain, binutils, Git, pkg-config, libpng and SDL2 development inputs, Bubblewrap and working 32-bit and 64-bit C compile/run environments. The builder installs nothing and fetches nothing. Existing extracted inputs can be supplied through `--sysroot` and `--multilib-sysroot`. `--check` runs the ABI probes in the same sandbox and inputs as the real build without exporting the species catalogue or compiling the game. Do not skip those probes or bypass a sandbox refusal.

## Standalone versus app world linkage

The engine's plain `make -f Makefile.native native BITS=64` is not the app world cohort. Its generated-world script consumers must use the same `PORTABLE` guard as the real generated-map producer. The native player-control service is real host code that does not depend on app world state, so it is built for `PLATFORM_NATIVE` as well as `PORTABLE`. The app retains its generated-map events and its world runtime callbacks. No replacement stubs supply missing game symbols.

The standalone opening/debug replay expectations include the real party-progress and battle diagnostics added to the inspector. Existing normalized state lines and image/hash expectations are preserved. Passing these replays checks standalone behavior only. Combined app gameplay and the final release build still require the integrator's frozen cohort and acceptance run.

## Before a private release handoff

1. Independently review the candidate source commits. The engine must contain the reviewed world/build repairs before the app's final gitlink and `PIN` are paired.
2. Have the release integrator set the final pin and version together. Confirm `--check` on a clean exact engine checkout.
3. Build the complete frozen app cohort and verify its mandatory checks. Record the binary/symbol hashes and actual platform acceptance. Targeted object compilation is not a complete release build.
4. Produce packages through the reviewed packaging path. Share only through the approved private handoff. Do not publish a game binary, ROM, save or asset-bearing archive as a public CI artifact.
5. Coordinate installation with the human's closed game and preserve trainer backups. Hosted-service deployment needs its own backup/rollback and connected-player coordination. Neither is performed by this build repair.
