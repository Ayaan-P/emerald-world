# Run in the pinned donor directory. Keep its source and ABI unchanged.
include Makefile.native
EW_ADAPTER := ../../build/expansion-presence.o
EW_PEERS := ../../build/expansion-peers.o
EW_LINK := ../../build/expansion-link.o
EW_CABLE := ../../build/expansion-cable.o
OBJS += $(EW_ADAPTER) $(EW_PEERS) $(EW_LINK) $(EW_CABLE)
# A relocated multilib sysroot does not contain the host's SDL dependencies.
# Resolve those at link time only; do not bake a private runtime search path.
NATIVE_LDFLAGS += -Wl,--wrap=frame_run -Wl,--wrap=SaveObjectEvents -Wl,--wrap=CopyPartyAndObjectsToSave -Wl,--wrap=GetObjectEventIdByPosition -Wl,-rpath-link,/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/pulseaudio
$(NATIVE_EXE): $(EW_ADAPTER) $(EW_PEERS) $(EW_LINK) $(EW_CABLE)
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
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -DPORTABLE -iquote ../../include -c $< -o $@
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
