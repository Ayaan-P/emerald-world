# Run in the pinned donor directory. Keep its source and ABI unchanged.
include Makefile.native
EW_DEXNAV_CONFIG := ../../build/expansion-dexnav-config.h
EW_DEXNAV := ../../build/expansion-dexnav.o
CPPFLAGS += -include $(EW_DEXNAV_CONFIG)
EW_CAVE := ../../build/expansion-cave.o
EW_CAVE_GEOMETRY := ../../build/expansion-cave-geometry.o
EW_CONTROL := ../../build/expansion-control.o
EW_CONTROL_TRANSPORT := ../../build/expansion-control-transport.o
EW_ADAPTER := ../../build/expansion-presence.o
EW_PEERS := ../../build/expansion-peers.o
EW_LINK := ../../build/expansion-link.o
EW_CABLE := ../../build/expansion-cable.o
EW_ACTIVITY := ../../build/expansion-activity.o
EW_TRADE_VALIDATE := ../../build/expansion-trade-validate.o
EW_TRADE_SAVE := ../../build/expansion-trade-save.o
OBJS += $(EW_DEXNAV) $(EW_CAVE) $(EW_CAVE_GEOMETRY) $(EW_CONTROL) $(EW_CONTROL_TRANSPORT) $(EW_ADAPTER) $(EW_PEERS) $(EW_LINK) $(EW_CABLE) $(EW_ACTIVITY) $(EW_TRADE_VALIDATE) $(EW_TRADE_SAVE)
# A relocated multilib sysroot does not contain the host's SDL dependencies.
# Resolve those at link time only; do not bake a private runtime search path.
NATIVE_LDFLAGS += -Wl,--wrap=frame_run -Wl,--wrap=SaveObjectEvents -Wl,--wrap=CopyPartyAndObjectsToSave -Wl,--wrap=GetObjectEventIdByPosition -Wl,--wrap=FieldGetPlayerInput -Wl,--wrap=LinkFullSave_SetLastSectorSignature -Wl,-rpath-link,/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/pulseaudio
$(NATIVE_EXE): $(EW_DEXNAV) $(EW_CAVE) $(EW_CAVE_GEOMETRY) $(EW_CONTROL) $(EW_CONTROL_TRANSPORT) $(EW_ADAPTER) $(EW_PEERS) $(EW_LINK) $(EW_CABLE) $(EW_ACTIVITY) $(EW_TRADE_VALIDATE) $(EW_TRADE_SAVE)
$(EW_ADAPTER): ../expansion_presence.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@


$(EW_PEERS): ../expansion_peers.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

# Reuse Emerald World's engine-independent, bounded LINK protocol and virtual
# cable state machine. PORTABLE is defined only for these two isolated objects.
$(EW_LINK): ../../src/platform/link_transport.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -DPORTABLE -DEMERALD_WORLD_EXPANSION_LINK -iquote ../../include -c $< -o $@
$(EW_CABLE): ../../src/platform/native_link.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -DPORTABLE -iquote ../../include -c $< -o $@

# Build a generated, fail-closed overlay of the pinned donor's link engine.
# It imports the existing world's validated native command handling while
# leaving the donor checkout untouched. The original dependency scan still
# covers its unchanged asset includes.
EW_PATCHED_LINK := ../../build/expansion-link-game.c
$(EW_PATCHED_LINK): src/link.c ../../src/link.c ../../scripts/patch_expansion_link.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_link.py src/link.c ../../src/link.c $@
$(C_BUILDDIR)/link.o: $(EW_PATCHED_LINK) $(C_FILTER_SCRIPT) ../../include/platform/native_link.h
	@echo "$(TARGET_CC) <Expansion link overlay> -o $@"
	@$(CPP) $(CPPFLAGS) -iquote ../../include $(EW_PATCHED_LINK) | $(PREPROC) -i -g $(ASSETS_DIR_NAME) $(EW_PATCHED_LINK) charmap.txt | $(C_FILTER) > $(C_PREPROCESSED) && $(TARGET_CC) $(CFLAGS) -c -x c -o $@ $(C_PREPROCESSED); status=$$?; rm -f $(C_PREPROCESSED); exit $$status

$(EW_ACTIVITY): ../expansion_activity.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -iquote ../../include -c $< -o $@

EW_PATCHED_CABLE := ../../build/expansion-cable-game.c
$(EW_PATCHED_CABLE): src/cable_club.c ../../scripts/patch_expansion_cable.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_cable.py src/cable_club.c $@
$(C_BUILDDIR)/cable_club.o: $(EW_PATCHED_CABLE) $(C_FILTER_SCRIPT)
	@echo "$(TARGET_CC) <Expansion cable battle overlay> -o $@"
	@$(CPP) $(CPPFLAGS) $(EW_PATCHED_CABLE) | $(PREPROC) -i -g $(ASSETS_DIR_NAME) $(EW_PATCHED_CABLE) charmap.txt | $(C_FILTER) > $(C_PREPROCESSED) && $(TARGET_CC) $(CFLAGS) -c -x c -o $@ $(C_PREPROCESSED); status=$$?; rm -f $(C_PREPROCESSED); exit $$status

$(EW_TRADE_VALIDATE): ../expansion_trade_validate.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

# Port party/consent validation, but do not expose the trade menu until the
# complete native trade/save workflow has been verified.
EW_PATCHED_TRADE := ../../build/expansion-trade-game.c
$(EW_PATCHED_TRADE): src/trade.c ../../src/trade.c ../../scripts/patch_expansion_trade.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_trade.py src/trade.c ../../src/trade.c $@
$(C_BUILDDIR)/trade.o: $(EW_PATCHED_TRADE) $(C_FILTER_SCRIPT) ../../include/platform/native_link.h
	@echo "$(TARGET_CC) <Expansion trade guard overlay> -o $@"
	@$(CPP) $(CPPFLAGS) -iquote src -iquote ../../include $(EW_PATCHED_TRADE) | $(PREPROC) -i -g $(ASSETS_DIR_NAME) $(EW_PATCHED_TRADE) charmap.txt | $(C_FILTER) > $(C_PREPROCESSED) && $(TARGET_CC) $(CFLAGS) -c -x c -o $@ $(C_PREPROCESSED); status=$$?; rm -f $(C_PREPROCESSED); exit $$status

$(EW_TRADE_SAVE): ../expansion_trade_save.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -iquote ../../include -c $< -o $@

# Reuse the bounded player protocol; its endpoint is never opened unless opted in.
$(EW_CONTROL): ../expansion_control.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -DPORTABLE -iquote ../../include -c $< -o $@
$(EW_CONTROL_TRANSPORT): ../../src/platform/player_control.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -DPORTABLE -iquote ../../include -c $< -o $@

# An isolated reserved map-group overlay for disposable offline cave tests.
$(EW_CAVE): ../expansion_cave.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
$(EW_CAVE_GEOMETRY): ../cave_geometry.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
EW_CAVE_OVERWORLD := ../../build/expansion-cave-overworld.c
$(EW_CAVE_OVERWORLD): src/overworld.c data/maps/map_groups.json ../../scripts/patch_expansion_cave.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_cave.py overworld src/overworld.c data/maps/map_groups.json $@
$(C_BUILDDIR)/overworld.o: $(EW_CAVE_OVERWORLD) $(C_FILTER_SCRIPT)
	@echo "$(TARGET_CC) <Expansion cave overworld overlay> -o $@"
	@$(CPP) $(CPPFLAGS) -iquote src $(EW_CAVE_OVERWORLD) | $(PREPROC) -i -g $(ASSETS_DIR_NAME) $(EW_CAVE_OVERWORLD) charmap.txt | $(C_FILTER) > $(C_PREPROCESSED) && $(TARGET_CC) $(CFLAGS) -c -x c -o $@ $(C_PREPROCESSED); status=$$?; rm -f $(C_PREPROCESSED); exit $$status
EW_CAVE_SAVE := ../../build/expansion-cave-save.c
$(EW_CAVE_SAVE): src/save.c data/maps/map_groups.json ../../scripts/patch_expansion_cave.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_cave.py save src/save.c data/maps/map_groups.json $@
$(C_BUILDDIR)/save.o: $(EW_CAVE_SAVE) $(C_FILTER_SCRIPT)
	@echo "$(TARGET_CC) <Expansion cave save overlay> -o $@"
	@$(CPP) $(CPPFLAGS) -iquote src $(EW_CAVE_SAVE) | $(PREPROC) -i -g $(ASSETS_DIR_NAME) $(EW_CAVE_SAVE) charmap.txt | $(C_FILTER) > $(C_PREPROCESSED) && $(TARGET_CC) $(CFLAGS) -c -x c -o $@ $(C_PREPROCESSED); status=$$?; rm -f $(C_PREPROCESSED); exit $$status

# CI-only file relay. Never enable for a distributed/user executable.
ifeq ($(EW_FAKE_FILE_LINK),1)
EW_FAKE_LINK := ../../build/expansion-fake-link.o
OBJS += $(EW_FAKE_LINK)
$(NATIVE_EXE): $(EW_FAKE_LINK)
NATIVE_LDFLAGS += -Wl,--wrap=LinkTransport_Init -Wl,--wrap=LinkTransport_Pump -Wl,--wrap=LinkTransport_Ready -Wl,--wrap=LinkTransport_Offer -Wl,--wrap=LinkTransport_OfferPending -Wl,--wrap=LinkTransport_PendingInvitation -Wl,--wrap=LinkTransport_Accept -Wl,--wrap=LinkTransport_Reject
$(EW_FAKE_LINK): ../../test/expansion_projection/fake_link_files.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -DPORTABLE -iquote ../../include -c $< -o $@
endif

# Enable the pinned donor's complete DexNav implementation at build time;
# its transient unlock flag stays off unless explicitly enabled at runtime.
$(EW_DEXNAV_CONFIG): include/config/dexnav.h ../../scripts/patch_expansion_dexnav.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_dexnav.py config $< $@
$(OBJS): $(EW_DEXNAV_CONFIG)
$(EW_DEXNAV): ../expansion_dexnav.c $(EW_DEXNAV_CONFIG)
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

EW_DEXNAV_GAME := ../../build/expansion-dexnav-game.c
$(EW_DEXNAV_GAME): src/dexnav.c ../../scripts/patch_expansion_dexnav.py
	@mkdir -p $(@D)
	python3 ../../scripts/patch_expansion_dexnav.py source $< $@
$(C_BUILDDIR)/dexnav.o: $(EW_DEXNAV_GAME) $(C_FILTER_SCRIPT)
	@echo "$(TARGET_CC) <Expansion DexNav overlay> -o $@"
	@$(CPP) $(CPPFLAGS) -iquote src $(EW_DEXNAV_GAME) | $(PREPROC) -i -g $(ASSETS_DIR_NAME) $(EW_DEXNAV_GAME) charmap.txt | $(C_FILTER) > $(C_PREPROCESSED) && $(TARGET_CC) $(CFLAGS) -c -x c -o $@ $(C_PREPROCESSED); status=$$?; rm -f $(C_PREPROCESSED); exit $$status
