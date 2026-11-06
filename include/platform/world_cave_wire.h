#ifndef GUARD_PLATFORM_WORLD_CAVE_WIRE_H
#define GUARD_PLATFORM_WORLD_CAVE_WIRE_H
#ifdef PORTABLE
#ifndef GENERATED_CAVE_PROFILES
#define GENERATED_CAVE_PROFILES 0
#endif
#ifndef GENERATED_CAVE_WILDLIFE
#define GENERATED_CAVE_WILDLIFE 0
#endif
#define WORLD_CAVE_WILDLIFE_BYTES 37
#ifndef GENERATED_MAP_LARGE
#define GENERATED_MAP_LARGE 0
#endif
#ifndef GENERATED_MAP_WILDS
#define GENERATED_MAP_WILDS 0
#endif
#ifndef GENERATED_WILDS_GUIDE
#define GENERATED_WILDS_GUIDE 0
#endif
#ifndef GENERATED_WILDS_CAST
#define GENERATED_WILDS_CAST 0
#endif
#ifndef GENERATED_WILDS_EVENTS
#define GENERATED_WILDS_EVENTS 0
#endif
#ifndef GENERATED_WILDS_SHARED_TERRAIN
#define GENERATED_WILDS_SHARED_TERRAIN 0
#endif
#ifndef GENERATED_WILDS_SHARED_GEOMETRY
#define GENERATED_WILDS_SHARED_GEOMETRY 0
#endif
#ifndef GENERATED_WILDS_LARGE_TERRAIN
#define GENERATED_WILDS_LARGE_TERRAIN 0
#endif
#define WORLD_CAVE_TERRAIN_MAX_BYTES (GENERATED_WILDS_LARGE_TERRAIN ? 1539 : 193)
#define WORLD_CAVE_EVENT_BYTES 1466
#define WORLD_CAVE_GUIDE_BYTES 59
#define WORLD_CAVE_CAST_BYTES 184
#define WORLD_CAVE_XL_CELLS (127 * 127)
#define WORLD_CAVE_LARGE_SIDE 63
#define WORLD_CAVE_LARGE_CELLS (WORLD_CAVE_LARGE_SIDE * WORLD_CAVE_LARGE_SIDE)
#define WORLD_CAVE_SIDE 31
#define WORLD_CAVE_CELLS (WORLD_CAVE_SIDE * WORLD_CAVE_SIDE)
#define WORLD_CAVE_ID 64
struct WorldCaveWire
{
#if GENERATED_MAP_LARGE
    u8 cells[WORLD_CAVE_LARGE_CELLS];
#else
    u8 cells[WORLD_CAVE_CELLS];
#endif
    char id[WORLD_CAVE_ID + 1];
    u8 nextRow;
    u8 version, profile;
    u8 wildlife[WORLD_CAVE_WILDLIFE_BYTES];
    bool8 wildlifeSeen;
    u8 guide[WORLD_CAVE_GUIDE_BYTES];
    bool8 guideSeen;
#if GENERATED_WILDS_CAST
    u8 cast[WORLD_CAVE_CAST_BYTES];
    bool8 castSeen;
#endif
#if GENERATED_WILDS_EVENTS
    u8 events[WORLD_CAVE_EVENT_BYTES];
    u8 nextEventChunk;
#endif
#if GENERATED_WILDS_SHARED_TERRAIN
    u8 terrain[WORLD_CAVE_TERRAIN_MAX_BYTES];u16 terrainSize;u32 terrainRevision;bool8 terrainSeen;
#if GENERATED_WILDS_LARGE_TERRAIN
    u8 terrainChunkNext, terrainChunkTotal;bool8 terrainLargeFraming;
#endif
#endif
    bool8 active;
};
/* 0: accepted partial; 1: complete; -1: invalid. Only BEGIN/ROW/END. */
int WorldCaveWire_Feed(struct WorldCaveWire *wire, unsigned count, const char *const *tokens);
void WorldCaveWire_Reset(struct WorldCaveWire *wire);
bool8 WorldCaveWire_ValidId(const char *id);
void WorldCaveWire_XLEventDigest(const u8 *events,const u8 *cast,const u8 *cells,char hex[65]);
void WorldCaveWire_XLPaintedEventDigest(const u8 *events,const u8 *cast,const u8 *cells,char hex[65]);
void WorldCaveWire_XLStableStoryDigest(const u8 *events,const u8 *cast,const u8 *worldId,char hex[65]);
#endif
#endif
