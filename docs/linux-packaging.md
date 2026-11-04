# Linux player releases

The Linux x86_64 archive contains the native executable, prebuilt React files, Python world modules and the generated `world/map_catalog.json` safety catalog. It runs without a checkout, npm, pip or a development virtual environment. It is **not** an AppImage or a self-contained operating-system runtime.

## Runtime requirements

- Linux x86_64 with glibc 2.35 or newer. Ubuntu 22.04 is the oldest intended distribution baseline. A binary built against newer glibc may raise the minimum recorded in `manifest.json`. Building on a newer distribution does not establish Ubuntu 22.04 compatibility.
- A standalone Python 3.11 or newer with its standard library, including `ssl`, `sqlite3`, `ctypes`, `fcntl` and `http.server`. Ubuntu 22.04's default Python 3.10 is not sufficient. Select an already installed newer interpreter explicitly. The installer uses its base executable rather than pinning a development venv.
- System SDL2 (`libSDL2-2.0.so.0`) and every native library listed in the manifest, including their transitive dependencies. These are resolved by the system dynamic loader. Nothing is copied from a development sysroot and no runtime libraries are synthesized.
- Bubblewrap (`bwrap`) and Xephyr on PATH. The system must permit the existing sandbox's unprivileged user namespaces. Xephyr needs X11 or XWayland. A working default browser is needed for the React launcher. Local world hosting additionally needs `openssl` on PATH. The optional mechanic worker uses `/usr/bin/python3` inside its existing sandbox.

The installer does not download or install any of these dependencies. Ask the distribution administrator to supply missing dependencies. Tkinter is not required for the packaged React entrypoint. The separate source Tk launcher still has its own requirements.

`entry.py --check` checks release integrity, interpreter version, glibc, native library resolution and command availability. It does not start a game, a display or a browser. It does not prove that namespace policy, the desktop DISPLAY or the browser work. Real game acceptance remains a separate release gate.

## Maintainer build workflow

Use trusted release inputs from the same integrated revision. Restore required upstream build assets, rebuild the Linux native executable and rebuild `launcher-web/dist` first using the project's existing build instructions. The packager does not build or download dependencies. Build/test commands for the native engine remain in `INSTALL_PC.md` and `test/headless/README.md`.

Run from the integrated checkout, after the packaging commit and launcher changes have been integrated:

```sh
python3 -m unittest test.world.test_linux_package -v
python3 -B -m world.build_catalog --check
python3 scripts/linux_package.py \
  --binary build/pokeemerald64 \
  --web-dist launcher-web/dist \
  --version 0.2.0-rc.1 \
  --output /home/ayaan/projects/emerald-world-research/releases/linux-0.2.0-rc.1
```

The output directory must not already exist. The publication tag is `v0.2.0-rc.1`. The manifest/package version is `0.2.0-rc.1`.

Outputs are `EmeraldWorld-0.2.0-rc.1-linux-x86_64.tar.gz` and a matching `.tar.gz.sha256` file. Every payload file has a SHA-256 and normalized mode in the embedded manifest. The tar and gzip metadata are normalized, so identical inputs produce identical bytes. `readelf` is a build-time prerequisite. It inspects the supplied ELF without executing it and records native dependencies and the glibc floor. Build-machine RPATH/RUNPATH is rejected.

No upload or publication is performed. The release operator must verify provenance, permissions to distribute and final human acceptance before publishing. Checksums detect accidental modification, not malicious replacement of a bundle together with its manifest. Obtain the external archive checksum from a trusted release channel.

### Privacy boundary

Only Git-tracked top-level `world/*.py`, the explicit map catalog, three fixed packaging/helper scripts, the supplied ELF and approved web asset extensions are included. No recursive source checkout, dependency sysroot, venv, trainer profile, database, invitation, save, source map or dotfile is copied. Links and special files are refused. An unexpected frontend artifact fails the build rather than being silently shipped. Frontend index references must resolve to local packaged files.

Allowlisting filenames is not content auditing. Only supply clean, trusted native/frontend builds and reviewed tracked source. Do not put credentials or private data inside an otherwise allowed JavaScript, image or ELF. The packager cannot establish the provenance of arbitrary supplied executable bytes.

## Install and update

Extract the archive as your normal user, preserving Unix file modes. Choose an installed standalone Python 3.11+ executable. For example, use `PYTHON=python3.11` only if that interpreter already exists on your machine.

```sh
sha256sum -c EmeraldWorld-0.2.0-rc.1-linux-x86_64.tar.gz.sha256
tar -xzf EmeraldWorld-0.2.0-rc.1-linux-x86_64.tar.gz
cd EmeraldWorld-0.2.0-rc.1-linux-x86_64
PYTHON=python3.11
"$PYTHON" -I install.py --help
"$PYTHON" -I install.py --check
"$PYTHON" -I entry.py --check
"$PYTHON" -I install.py
```

If your preferred interpreter is not the one running the installer, add `--python /absolute/path/to/python3.11`. `install.py --check` verifies only the extracted files and selected standalone interpreter without creating installation state. `entry.py --check` additionally checks native and desktop prerequisites. It exits nonzero with `MISSING` lines if these are absent.

The default install creates:

```text
~/.local/share/emerald-world-player/releases/0.2.0-rc.1/
~/.local/share/emerald-world-player/current -> releases/0.2.0-rc.1
~/.local/share/applications/emerald-world-player.desktop
```

Open **Emerald World** in the application menu. You can also run `"$PYTHON" -I ~/.local/share/emerald-world-player/current/entry.py`, or run `entry.py` directly from an extracted bundle. Neither command requires a source checkout. The menu entry pins the verified standalone Python executable, so keep that interpreter installed. No shell-profile modification is needed.

Extract a newer version separately and rerun its `install.py`. The installer validates every payload file before copying, validates the copied release, and atomically switches `current`. Old versions remain in `releases`. Same-version installs are idempotent only when all installed bytes, modes and manifest match. Modified existing releases are never overwritten. Do not edit files in a release directory or run tools that create bytecode caches there.

Player data remains in `~/.local/share/emerald-world/worlds`, the same default as the existing launcher. Install/update never reads, copies, deletes or rewrites that tree. Close the game before updating or rolling back. To roll back, rerun `install.py` from the previously extracted trusted archive. This switches code only and cannot reverse changes to a save made by a newer game version. Take save backups before changing versions.

`--prefix /absolute/path` and `--applications-dir /absolute/path` support alternate installation destinations. Use separate, non-linked directories outside the extracted archive. The installer refuses unmanaged shortcut collisions and non-managed `current` paths. Install only into a directory writable by you and not shared with untrusted concurrent writers.

### Existing source launchers

Installation intentionally does **not** touch `~/.local/bin/emerald-world`, `emerald-world.desktop`, or `emerald-world-react.desktop`. An existing custom/source launcher continues to launch its old checkout. Use the new `emerald-world-player.desktop` entry to migrate without overwriting anything:

```sh
gtk-launch emerald-world-player
```

If you want to retire the old launcher, inspect it and move it aside yourself after confirming the packaged release works. Do not remove its worlds or saves. No automatic migration of commands or private profiles is performed.

## Verification scope

`python3 -m unittest test.world.test_linux_package -v` compiles a tiny disposable real C executable, builds real archives and checks checksums, reproducibility, invalid inputs, installation, idempotence, update, collision protection, corruption rejection and save-sentinel preservation. It never substitutes the actual game binary for package tests. A runtime-conditional test opens the real packaged loopback launcher with a capture-only `BROWSER` helper and a disposable HOME, fetches frontend assets and authenticated `/api/state`, then requests a clean quit. No game or GUI is started. This test skips explicitly when runtime prerequisites are absent.

After producing the actual release archive, repeat `entry.py --check` and the capture-browser loopback smoke on that exact extracted archive with a disposable HOME. Then perform the project's native engine/headless gates and the intended real Linux player acceptance. Fixture archive success is not a claim that the integrated game passed those gates.
