# Build the native PC port

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

## Opt-in native Expansion engine (Linux)

Vanilla remains the default. Expansion is a separate native executable, not a
mechanics patch for the vanilla engine. Initialize the pinned source and build:

```sh
git submodule update --init engines/expansion-native
python3 scripts/build_expansion.py --jobs 4
```

The source is `https://github.com/uehlbran/pokeemerald-expansion-native` at
`bb3fd057061cdd7e6a9e79b76abb41924ee44ecc`. Its scoped MIT license stays in
`engines/expansion-native/LICENSE`. It is not a blanket license for the game,
graphics, audio or other upstream assets. Do not redistribute built game assets,
saves or executables with this source integration.

The build uses the donor's `PLATFORM_NATIVE`, fixed-address GBA mappings, SDL
layer and native save implementation. It does not compile vanilla's `PORTABLE`
bridge against Expansion structs. Linux needs GCC/G++, Make, SDL2 and libpng
development files, Python 3 and Bubblewrap. The donor's 64-bit ABI checks also
compile and execute a 32-bit layout probe, so an i386 libc/GCC development
runtime is required even though the game is 64-bit. No dependency installation
or download is performed by the entry point. `--sysroot PATH` supplies an
existing extracted SDL2/libpng tree. `--multilib-sysroot PATH` supplies an
existing extracted multilib development tree when it is not installed on the
host. Missing prerequisites fail the build rather than disabling ABI checks.
The executable and callback symbol map are copied into `build/expansion-native/`.

Use an explicit disposable state directory for the first run:

```sh
python3 -m world.launcher --state-dir /absolute/path/expansion-test offline Ash --engine expansion-native --frames 120
# A full opening, save, cold restart and Continue using the donor's own replay:
python3 -m world.launcher --state-dir /absolute/path/expansion-test offline Ash --engine expansion-native --replay engines/expansion-native/tests/smoke/opening.replay
```

Omit `--frames` and use `--display :95` to play in an existing dedicated nested
X display. The Expansion selector is currently a CLI/session API feature, not
an option in the React or Tk launcher. It selects the Expansion executable unless
`--binary` is explicitly supplied. Vanilla flags, seed saves, online-save copying,
player-control endpoints and vanilla invitations are rejected for Expansion.
Donor `--replay` scripts are supported instead of vanilla input scripts.

An Expansion presence authority and a trainer can be started in separate terminals:

```sh
python3 -m world.launcher --state-dir /absolute/path/expansion-test host --engine expansion-native
python3 -m world.launcher --state-dir /absolute/path/expansion-test join Ash --engine expansion-native --display :95
```

Online profiles, identity database and sockets are under
`STATE/engines/expansion-native/`. Offline profiles are under
`STATE/.offline/engines/expansion-native/`. Vanilla `STATE/trainers/` is never
mounted into Expansion. The donor alone reads and writes its `PENSAVE` format.
No vanilla Pokemon structures, save blobs or party/bag ownership payloads are
copied into the donor.

The first bridge seam is read-only presence. A linked adapter samples the donor's
own inspection interface on its game thread and atomically publishes versioned
scalar map/position facts. The session's authenticated sidecar sends these to the
separate world authority and writes its snapshot to the profile's telemetry.
Expansion presence is always busy, with party/bag hashes marked unavailable.
It cannot participate in vanilla co-op and does not modify engine state.

**Multiplayer is not ported.** Missing functions include remote player sprites
and facing/graphics projection, shared tile/NPC edits and interactions, chat and
travel UI, invitations/remote hosting integration, native link transport and
synchronized battles, cooperative wild/trainer battles and catching, trades,
party/storage/ownership transfer, world menu and player-control endpoints,
shared story credit and Crossroads regions. The authority's catalog is still
vanilla Hoenn. Extra Expansion maps need their own catalog before presence can
be accepted there. A successful single-player replay or presence connection is
not multiplayer acceptance.

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
