# Private Windows Expansion handoff

This lane packages the actual Expansion engine, not the root `pokeemerald64.exe` made by the older `windows-client` workflow. It never uploads an artifact or release. Repository visibility does not make a GitHub artifact a safe private distribution channel.

The deliverable is a local ZIP for an explicitly authorized manual private handoff. It contains the x64 Expansion PE, its recursive non-system DLL closure, the matching committed `world` Python modules and browser UI source, a source guest entry point, and a hash/provenance manifest. It contains no invitation, certificate key, profile or save. Only committed allowlisted sources are selected. Untracked files cannot become payload just because they sit beside the game.

## What a friend needs

An x64 Windows PC with existing 64-bit Python 3.11 or later and tkinter is required for this **source guest** lane. There is no bundled Python interpreter or PyInstaller launcher. This is not a claim of a standalone installer.

Extract the complete archive into a new directory, then open `Start-Expansion.cmd`. The launcher verifies every payload hash before importing the guest modules. It binds the existing remote Windows guest UI to `game/pokeemerald-native.exe`. Saves use a separate `%LOCALAPPDATA%/EmeraldWorld/expansion-native` namespace, not the older vanilla guest namespace. A host must privately supply a fresh **Expansion** invitation and independently trusted TLS fingerprint. The browser UI directory is matching development source, not a prebuilt Windows browser host. Linux-only Bubblewrap session/hosting paths are not advertised as Windows features.

For a verification-only check, without starting the game or accessing a profile:

```powershell
py -3 scripts/windows_expansion_entry.py --verify
```

`--self-test` additionally checks tkinter on Windows without joining a world. Neither command proves multiplayer gameplay or compatibility with a real friend's Windows device. The manifest is an integrity/cohort record, not a cryptographic signature. Receive the ZIP hash from the maintainer over a trusted private channel.

## Build on an authorized Linux x64 machine

Use a **dedicated clean app and nested engine checkout**. Do not use the parent integration worker's existing full build. Before building, integrate the final source changes, commit the engine and pin its gitlink in the app, then commit the app. Both pins must be full lowercase 40-character commit IDs. No development/dirty cohort is permitted. The worker base is not the final release pin.

Existing prerequisites are Linux x64, GNU host development tools including SDL2 and libpng, a working host 32-bit C compile/run ABI, clang's COFF assembler, MinGW-w64 x64 GCC/binutils, Bubblewrap network namespaces, and the engine's already-extracted SDL2 2.30.12 MinGW SDK. The SDK must already have its `.unpacked` stamp, headers, import library and `SDL2.dll` in `engines/expansion-native/build/sdl2-mingw`. This lane does not install, fetch or repair any of them. A missing prerequisite is a hard, actionable failure.

Set these local variables to the actual final commits and your dedicated checkout. Do not copy shortened example pins:

```bash
APP=/absolute/path/to/dedicated/app
APP_PIN=$(git -C "$APP" rev-parse HEAD)
ENGINE_PIN=$(git -C "$APP/engines/expansion-native" rev-parse HEAD)
python3 "$APP/scripts/windows_expansion_build.py" --app "$APP" \
  --app-pin "$APP_PIN" --engine-pin "$ENGINE_PIN" --check
python3 "$APP/scripts/windows_expansion_build.py" --app "$APP" \
  --app-pin "$APP_PIN" --engine-pin "$ENGINE_PIN" --jobs 4
```

The builder refuses pre-existing engine object trees, rather than silently reusing a differently flagged cohort or deleting someone else's output. Rebuild in another clean dedicated checkout if a build was interrupted. The existing SDK directory may be reused. Source initialization and any tool provisioning require separate authorization.

The builder explicitly runs the app's `engines/expansion.mk` through a generated wrapper for **both** passes. The first builds and checks the 64-bit ELF data and its COFF conversion. The second sets `WINDOWS_DATA_CHECKED=1` so the donor cannot silently recurse into its unwrapped vanilla Makefile. The wrapper removes the Linux-only `rpath-link` option from the Windows link and adds Winsock. It does not modify the shared integration Makefile. Network access is disabled by Bubblewrap, inherited credential environment is cleared, and only the dedicated engine tree is writable. The SDK download stamp is treated as already made.

The fixed RC12 cohort is:

```
BITS=64 TARGET_OS=windows TEST=0 SANITIZE=0
EW_REGION_STATE=1 EW_KANTO_CONTENT=1 GENERATED_WORLD_REGIONS=1
MAP_VERSION=combined
```

The receipt includes command arrays, wrapper contents/hash, source-module hashes, exact app/engine pins, integration-Makefile hash, SDK hashes, tool paths/versions, and engine SHA-256. The compiler-exported species catalogue must byte-match the committed app catalogue before a receipt is issued. If it differs, regenerate and commit the correct catalogue as part of the final cohort, then rebuild. Do not rewrite a receipt to bypass this gate.

## Assemble the private ZIP locally

After a successful build, use only reviewed DLL directories. The packager selects the engine PE from the fixed nested-engine output path. There is deliberately no `--binary` override that could accidentally select the root vanilla executable.

```bash
ENGINE="$APP/engines/expansion-native"
python3 "$APP/scripts/windows_expansion_package.py" --app "$APP" \
  --app-pin "$APP_PIN" --engine-pin "$ENGINE_PIN" \
  --receipt "$ENGINE/build/native64-windows/windows-expansion-build.json" \
  --dll-dir "$ENGINE/build/native64-windows" \
  --objdump x86_64-w64-mingw32-objdump \
  --output /absolute/private/directory/RC12-Expansion-Windows.zip \
  --private-handoff
```

Add another explicit `--dll-dir` for an already-installed MinGW runtime DLL directory if required. Do not pass an entire SDK bin directory when the same `SDL2.dll` is already in the engine output. Duplicate case-insensitive DLL candidates fail as ambiguous. Recursive imports must resolve to an explicit reviewed OS-DLL list/API sets or a bundled x64 PE DLL. Delay-import tables are rejected rather than silently omitted. Every file and every DLL edge appears in `provenance.json`. The ZIP has deterministic entries and is created mode 0600 on POSIX. It is read back and hash-checked before its SHA-256 is printed. The output must be new and paths must not traverse symlinks, hardlinks, reparse points or Windows reserved device names.

Keep the archive local until a maintainer authorizes its specific private recipient/channel. Never attach this ZIP, native binary, UI art, save or profile to public GitHub artifacts/releases. Do not change repository visibility. The new `windows-expansion-source-gates` workflow runs only source/synthetic-fixture contracts and prints text. It uploads nothing and does not dispatch a build.

## Acceptance and current evidence boundary

Run the contract tests locally with:

```bash
python3 -m unittest test.test_windows_expansion_delivery -v
```

The PE bytes in unit tests are synthetic fixtures. Successful packaging/extraction tests are not an actual game build. At implementation time this Linux worker had no MinGW compiler/binutils, no clang, no Wine, and no authorized Windows remote/device supplied. Therefore no actual PE build, Wine runtime or Windows device acceptance was performed. Nothing was installed, downloaded, uploaded, dispatched or remotely executed. After the parent pins the final cohort, a maintainer with the existing prerequisites must rebuild and perform these gates:

- Inspect the real built PE and all non-system DLL hashes/import edges.
- Verify a fresh archive on Windows x64, then run its Tk self-test.
- Import a fresh private Expansion invitation. Check fresh native telemetry reaches online, not merely a live process or local tunnel.
- Exercise movement, menu, sound, save/restart, remote friend visibility, reconnect and a safe shared interaction against the matching host cohort.
- Confirm separate Expansion profiles, no credential/save leakage, and no fallback to a vanilla engine.

If Wine later becomes available, record its exact version and results separately. Wine is not a friend's Windows PC and does not replace the final device gate. A source-only gate or missing runtime must never be represented as a passed release/device gate.
