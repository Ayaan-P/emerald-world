# Run in the pinned donor directory; this integration may live elsewhere.
EW_INTEGRATION_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
EW_ROOT := $(abspath $(EW_INTEGRATION_DIR)/..)
# Propagate the exact same feature cohort to recursive pointer4 reference builds.
# Appending CPPFLAGS only after inclusion leaves the ABI checker comparing two
# different games (vanilla scripts against world scripts).
# Connected-place admission is opt-in until full native acceptance.
GENERATED_WORLD_REGIONS ?= 0
EW_REGION_STATE ?= 0
EW_KANTO_CONTENT ?= 0
export NATIVE_EXTRA_CPPFLAGS := -DGENERATED_WORLD_REGIONS=$(GENERATED_WORLD_REGIONS) -DPORTABLE=1 -DCOOP_FULL_SIX_READY=1 -DGENERATED_MAP_READY=1 -DGENERATED_MAP_AUTOTILE=1 -DGENERATED_MAP_LARGE=1 -DGENERATED_MAP_WILDS=1 -DGENERATED_CAVE_PROFILES=1 -DGENERATED_CAVE_BIOMES=1 -DGENERATED_CAVE_WILDLIFE=1 -DWORLD_EXTENDED_OBJECTS=1 -DWORLD_EXTENDED_SPRITES=1 -DWORLD_NATIVE_OAM=1 -DWORLD_NATIVE_TILEBANK=1 -DWORLD_MATCHED_TRAINERS=1 -DWORLD_SMOOTH_PRESENCE=1 -DGENERATED_WILDS_GUIDE=1 -DGENERATED_WILDS_CAST=1 -DGENERATED_WILDS_EVENTS=1 -DGENERATED_WORLD_XL=1 -DGENERATED_WILDS_SHARED_TERRAIN=1 -DGENERATED_WILDS_SHARED_GEOMETRY=1 -DGENERATED_WILDS_LARGE_TERRAIN=1
export NATIVE_EXTRA_CPPFLAGS += -DEW_REGION_STATE=$(EW_REGION_STATE) -DEW_KANTO_CONTENT=$(EW_KANTO_CONTENT)
include Makefile.native
# A relocated multilib sysroot does not contain the host's SDL dependencies.
# Resolve those at link time only; do not bake a private runtime search path.
NATIVE_LDFLAGS += -Wl,--defsym=gba_native_vram_size=0x20000 -Wl,-rpath-link,/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/pulseaudio
