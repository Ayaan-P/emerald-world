# Run in the pinned donor directory. Keep its source and ABI unchanged.
include Makefile.native
EW_ADAPTER := ../../build/expansion-presence.o
EW_PEERS := ../../build/expansion-peers.o
OBJS += $(EW_ADAPTER) $(EW_PEERS)
# A relocated multilib sysroot does not contain the host's SDL dependencies.
# Resolve those at link time only; do not bake a private runtime search path.
NATIVE_LDFLAGS += -Wl,--wrap=frame_run -Wl,--wrap=SaveObjectEvents -Wl,--wrap=CopyPartyAndObjectsToSave -Wl,-rpath-link,/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/pulseaudio
$(NATIVE_EXE): $(EW_ADAPTER) $(EW_PEERS)
$(EW_ADAPTER): ../expansion_presence.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@


$(EW_PEERS): ../expansion_peers.c
	@mkdir -p $(@D)
	$(TARGET_CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
