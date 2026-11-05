#ifndef GUARD_PLATFORM_WORLD_CAVE_WIRE_H
#define GUARD_PLATFORM_WORLD_CAVE_WIRE_H
#ifdef PORTABLE
#define WORLD_CAVE_SIDE 31
#define WORLD_CAVE_CELLS (WORLD_CAVE_SIDE * WORLD_CAVE_SIDE)
#define WORLD_CAVE_ID 64
struct WorldCaveWire
{
    u8 cells[WORLD_CAVE_CELLS];
    char id[WORLD_CAVE_ID + 1];
    u8 nextRow;
    bool8 active;
};
/* 0: accepted partial; 1: complete; -1: invalid. Only BEGIN/ROW/END. */
int WorldCaveWire_Feed(struct WorldCaveWire *wire, unsigned count, const char *const *tokens);
void WorldCaveWire_Reset(struct WorldCaveWire *wire);
#endif
#endif
