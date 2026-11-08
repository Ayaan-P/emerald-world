# Build from source

## RC10 Expansion on Linux

For the current game, follow the [README source setup](README.md#build-and-open-rc10-from-source-on-linux).
The root `make linux`, Windows and macOS targets below build the historical
vanilla port, not RC10. RC10 uses the pinned `engines/expansion-native` submodule
and `python3 scripts/build_expansion.py`. It does not need the root vanilla
asset-restoration command or an ARM/GBA toolchain.

On Debian/Ubuntu, the native build and isolated game require these packages
(install them explicitly with your package manager):

```sh
sudo apt install build-essential git make pkg-config libpng-dev libsdl2-dev gcc-multilib libc6-dev-i386 python3 bubblewrap xserver-xephyr
```

Use Python 3.11+, GNU make 4.2+ and Node.js/npm for `launcher-web`. The game needs
an X11/XWayland desktop and a browser. No 32-bit SDL2 is required for the 64-bit
RC10 binary, but a working 32-bit C compiler/runtime is required by the ABI
layout checks. Check the actual sandboxed toolchain before a long build:

```sh
git submodule sync --recursive
git submodule update --init --recursive
python3 scripts/build_expansion.py --check
python3 scripts/build_expansion.py
python3 -m world.web_launcher --check
```

The last check also expects the React UI to have been built as shown in the
README. Neither check installs packages or opens a game. The build check uses
only disposable files in its sandbox's private `/tmp`. If Bubblewrap cannot
create its sandbox, check your distribution's user-namespace policy rather
than running the builder as root.

## Historical vanilla port

These instructions build **pokeemerald** from source. For the current multiplayer
features, Linux launcher setup and evidence limits, see the [README](README.md)
and [co-op status](docs/COOP_STATUS.md). Native platform build targets do not
imply current Windows/macOS multiplayer acceptance. No ROM, save or executable
is supplied by this guide.

Use the current `main` source on both peers and rebuild both for co-op protocol
v3. A successful presence connection does not prove matching native versions.

The Linux section below includes cloning and restoring the three hash-pinned
upstream inputs. Windows and macOS builders also need those inputs: after
installing their platform tools and Python 3, run the same
`python3 scripts/restore_upstream_assets.py` and
`python3 scripts/restore_upstream_assets.py --check` commands from the checkout
before building. They restore only the manifest's ignored local build inputs.
Do not commit or redistribute them. No dependency installation is automatic.

## Windows 10/11 (WSL1)
Follow pret instructions on how to install WSL1 [here](INSTALL.md)

Install the following libraries

```
sudo apt install build-essential git make g++-mingw-w64-i686 g++-mingw-w64-x86-64 libpng-dev
```
Download SDL2 mingw libraries from [here](https://archive.org/download/sdl-2-2.0.16/SDL2-devel-2.0.16-mingw.tar.gz)

Extract the tar to the root of the project and rename the SDL2-2.0.16 folder to SDL2

Build the Windows version using all available CPU threads:

```
make -j"$(nproc)" winwsl WERROR=1
```

To build 32 bit version add `IS64BIT=0` to the end of the command above

You should get an executable named `pokeemerald(64 or 32).exe`

Download SDL2.dll [32 bit version](https://archive.org/download/sdl-2-2.0.16/SDL2-2.0.16-win32-x86.zip), [64 bit version](https://archive.org/download/sdl-2-2.0.16/SDL2-2.0.16-win32-x64.zip) and put it in the same place as the executable and you should be good to go

## Linux (Ubuntu)

Start from the current development baseline:

```sh
git clone --branch main https://github.com/Ayaan-P/emerald-world.git
cd emerald-world
```

Run the following command to install the required libraries
```
sudo apt install build-essential git make libpng-dev libsdl2-dev
```

Restore the three build inputs using the repository's existing hash-pinned
upstream manifest. They are local build inputs only, ignored by Git; do not
commit or redistribute them with this source baseline.

```sh
python3 scripts/restore_upstream_assets.py
python3 scripts/restore_upstream_assets.py --check
```

Build the Linux version:

```sh
make -j"$(nproc)" linux CFLAGS=-g WERROR=1
```

For the multiplayer desktop launcher, also install `python3-tk`, `bubblewrap`
and `xserver-xephyr` through your distribution's package manager. The launcher
checks prerequisites with `python3 scripts/linux_client.py --check`; it does not
install them automatically.

To build 32 bit version add `IS64BIT=0` to the end of the command above (32 bit version does not build on Ubuntu 25 and above)

You should get an executable named `pokeemerald(64 or 32)`

To build with clang instead of gcc, add `COMPILER=clang`.

## macOS

Install the Xcode command line tools with `xcode-select --install`, and [Homebrew](https://brew.sh). Then install the other tools and libraries:
```
brew install make pkg-config libpng sdl2 x86_64-elf-binutils
```

The game's data is assembled with the GNU assembler from `x86_64-elf-binutils`, because clang's assembler can't build it. Homebrew's `make` is a newer GNU make than the one macOS has, and it's run as `gmake`.

Build the macOS version with:
```
gmake macos -j$(sysctl -n hw.ncpu)
```

You should get an executable named `pokeemerald64`, which uses Homebrew's SDL2.

## GBA

Follow instructions in [INSTALL.md](INSTALL.md)


## RC12 cumulative candidate handoff

This candidate contains the entire app stack against main, with no merge or
release implied. Integrate this cumulative candidate once; do not also apply
all constituent patches a second time. The smaller drafts remain review slices.

Verified source inputs at preparation:

- App main: `80b14ebfbfd4dd4da2dc16d886a37f0db1f45516`.
- #279 privacy: `ebc93b91ec5c882ac08d8336af26da4ad943ee18`.
- #280 complete field story: `da328a772a80b3f0ea67b11aa254873c5c66fbdb`.
- #281 relays: `24bc0deca2b7803a3816a9d37cd8e69e25ef4f12`.
- #282 flag duels: `3f946f921ede2956e00644158a49973dd3906c19`.
- #283 activity board: `27c097d834bab56a3d27bf48fde15c5ddaf4a326`.
- Native main: `7d463da5613d9aa3c19f444c22de0be4424e2458`.
- Native #23 paired privacy client: `984165808a45aaaaa7c7169c228ef1a1480ab6d0`.

- Native #24 mounts and matched witness protocol: `488796e4959eb7f9d658abc7e8313e138acb3c87`.

The native gitlink and `scripts/build_expansion.py` pin both point at #24.
Native #24 (including #23) remains independently reviewable; its source must be available to the
build account. In a separate clean checkout, initialize the pinned submodule,
run `python3 scripts/build_expansion.py --check`, then use the supported build
instructions above. Do not reset a dirty integration checkout or substitute an
older executable. Rebuild/package the launcher and server with the same candidate.
If the native commit is rebased during integration, update both pins together.

### One player-facing batch

1. Run a disposable local world with two independent trainers and matched RC12
   clients. Each joins the same guild voluntarily. `/guild play` is the common
   entry; `/guild play list` lists installed games and starting locations.
2. Relays and flag duels ship as built-in Petalburg activities. Neither requires
   story installation, generated-area travel or save editing. A host starts one,
   then explicitly `/guild play share KIND`; a partner reads `/guild play open`
   and joins by host name. Adverts remain within the guild and expose no clues.
3. The owner installs the complete Two-Tower Signal through Local worlds →
   Author content → Cooperative field story, preview and confirmed apply.
   This publishes both the two-player puzzle and its linked follow-up together.
   It must be done with players disconnected. No puzzle is silently installed.
4. Puzzle stations are on ordinary Petalburg and Rustboro maps. After completion,
   read `/story` at the final location for eligible consequences. Races/duels
   report automatic movement events in the existing native chat strip.

### Privacy and acceptance boundaries

The paired client is required: capability negotiation and unknown/slash-command
fail-closed behavior must survive old-server connection, reconnect and forged
chat replies. Do not expose private activity features using an old client.
Native tests compile real parser/send/disconnect functions plus mount adapter
and ordered tile witness code; app tests cover
private routing and the real in-memory CHAT/STATE activity paths. None of these
assert that a rendered two-client playtest happened.

Local candidate verification: 65 activity/content/privacy/mount Python checks,
148 launcher UI tests and a production launcher build passed before pinning.
The five build-setup tests and native focused C privacy test also pass.
Full native compilation and rendered/internet multiplayer remain unverified in
this environment. Existing baseline CI had a private native-submodule checkout
credential failure; fix access through the normal repository setup, not an
alternate payload or security workaround. No dependencies were installed here.

Maya owns integration, QA and release. Acceptance still needs: a clean build of
the exact pin, mixed-version privacy checks, two visible clients walking the
source-checked stations/bases, relay handoff and flag tag feel, disconnect/rejoin,
completed-result restart persistence, and confirmation that independent normal
saves remain unchanged by these activities. Source collision/BFS checks are not
visual route QA. Field records use reported positions, not anti-cheat authority.


Mounted extension: `/mount SLOT` selects an owned conscious supported party
Pokemon. `/guild play start relay petalburg_mount1` is the distinct mounted
course. No Pokemon are granted. MOUNTS1 must be negotiated; no mounted race runs
on a foot-only/legacy peer. The paired protocol carries exact per-frame tile
witnesses so faster movement and turns survive six-frame network sampling.
Overflow or lost continuity cancels instead of inventing checkpoint visits.
Remote mounts use bounded extra sprites/palettes; resource exhaustion preserves
the trainer but may omit its mount. Add actual rider alignment, full native
compilation, two-client mount visibility, fastest turns and delayed-network race
behavior to Maya's acceptance checks. No such rendered playtest is claimed here.
