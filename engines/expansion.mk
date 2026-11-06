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
