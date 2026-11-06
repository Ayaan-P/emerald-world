# Native Expansion is the starting tree; this enables only the new presence slice.
include Makefile.native
CPPFLAGS += -DEW_WORLD_PRESENCE=1
