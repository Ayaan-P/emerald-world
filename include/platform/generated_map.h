#ifndef GUARD_PLATFORM_GENERATED_MAP_H
#define GUARD_PLATFORM_GENERATED_MAP_H

/* Experimental local instance. Never enable without native acceptance. */
#ifndef GENERATED_MAP_READY
#define GENERATED_MAP_READY 0
#endif

#ifndef GENERATED_MAP_AUTOTILE
#define GENERATED_MAP_AUTOTILE 0
#endif

#ifndef GENERATED_CAVE_PROFILES
#define GENERATED_CAVE_PROFILES 0
#endif

#ifndef GENERATED_CAVE_BIOMES
#define GENERATED_CAVE_BIOMES 0
#endif
#if GENERATED_CAVE_BIOMES && (!GENERATED_MAP_READY || !GENERATED_MAP_AUTOTILE || !GENERATED_CAVE_PROFILES)
#error GENERATED_CAVE_BIOMES requires generated maps, autotiling and cave profiles
#endif

#ifndef GENERATED_CAVE_WILDLIFE
#define GENERATED_CAVE_WILDLIFE 0
#endif
#if GENERATED_CAVE_WILDLIFE && (!GENERATED_MAP_READY || !GENERATED_CAVE_PROFILES)
#error GENERATED_CAVE_WILDLIFE requires generated maps and cave profiles
#endif

#ifndef GENERATED_WORLD_XL
#define GENERATED_WORLD_XL 0
#endif
#ifndef GENERATED_MAP_LARGE
#define GENERATED_MAP_LARGE 0
#endif
#if GENERATED_MAP_LARGE && !GENERATED_MAP_READY
#error GENERATED_MAP_LARGE requires generated maps
#endif

#ifndef GENERATED_MAP_WILDS
#define GENERATED_MAP_WILDS 0
#endif
#if GENERATED_MAP_WILDS && !GENERATED_MAP_LARGE
#error GENERATED_MAP_WILDS requires large generated maps
#endif

#ifndef GENERATED_WILDS_GUIDE
#define GENERATED_WILDS_GUIDE 0
#endif
#if GENERATED_WILDS_GUIDE && !GENERATED_MAP_WILDS
#error GENERATED_WILDS_GUIDE requires generated wilds
#endif

#ifndef GENERATED_WILDS_CAST
#define GENERATED_WILDS_CAST 0
#endif
#if GENERATED_WILDS_CAST && !GENERATED_WILDS_GUIDE
#error GENERATED_WILDS_CAST requires generated wilds guides
#endif

#ifdef PORTABLE
struct MapLayout;
struct WildPokemonInfo;
#define GENERATED_WILDLIFE_BYTES 37
#define GENERATED_MAP_TEMPLATE_BYTES (31 * 31)
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES (63 * 63)
#define GENERATED_GUIDE_BYTES 59
#ifndef GENERATED_WILDS_EVENTS
#define GENERATED_WILDS_EVENTS 0
#endif
#if GENERATED_WILDS_EVENTS && !GENERATED_WILDS_CAST
#error GENERATED_WILDS_EVENTS requires generated wilds casts
#endif
#ifndef GENERATED_WILDS_SHARED_TERRAIN
#define GENERATED_WILDS_SHARED_TERRAIN 0
#endif
#if GENERATED_WILDS_SHARED_TERRAIN && !GENERATED_WILDS_EVENTS
#error GENERATED_WILDS_SHARED_TERRAIN requires generated wilds events
#endif
#ifndef GENERATED_WILDS_SHARED_GEOMETRY
#define GENERATED_WILDS_SHARED_GEOMETRY 0
#endif
#if GENERATED_WILDS_SHARED_GEOMETRY && !GENERATED_WILDS_SHARED_TERRAIN
#error GENERATED_WILDS_SHARED_GEOMETRY requires shared terrain
#endif
#ifndef GENERATED_WILDS_LARGE_TERRAIN
#define GENERATED_WILDS_LARGE_TERRAIN 0
#endif
#if GENERATED_WILDS_LARGE_TERRAIN && !GENERATED_WILDS_SHARED_GEOMETRY
#error GENERATED_WILDS_LARGE_TERRAIN requires shared geometry
#endif
#if GENERATED_WORLD_XL && (!GENERATED_MAP_LARGE || !GENERATED_MAP_WILDS)
#error GENERATED_WORLD_XL requires large generated wilds
#endif
#define GENERATED_XL_MAP_BYTES (127 * 127)
#define GENERATED_TERRAIN_MAX_BYTES (GENERATED_WILDS_LARGE_TERRAIN ? 1539 : 193)
#define GENERATED_EVENT_BYTES 1466
#define GENERATED_CAST_BYTES 184
bool8 GeneratedMap_StageXLWilds(const u8 *cells, u32 size);
bool8 GeneratedMap_StageXLCast(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_StageXLEvents(const u8 *events,u32 eventSize,const u8 *cast,u32 castSize,const u8 *cells,u32 size);
bool8 GeneratedMap_StageTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_StageLargeTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_StageWildsTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_StageGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_StageEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size);
bool8 GeneratedMap_StageSharedEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size);
bool8 GeneratedMap_MatchesPreparedEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size);
void GeneratedMap_RunEvent(void);
u8 GeneratedMap_EventState(void);
bool8 GeneratedMap_SetSharedEventState(u8 state);
bool8 GeneratedMap_SetSharedEventRule(const u8 *rule, u32 size);
bool8 GeneratedMap_SetSharedEventTile(unsigned x, unsigned y, unsigned terrain);
bool8 GeneratedMap_SetSharedEventTiles(const u8 *patch, u32 size);
bool8 GeneratedMap_ValidateSharedTerrain(const u8 *patch, u32 size);
bool8 GeneratedMap_SharedTerrainNeedsGeometry(const u8 *patch, u32 size);
bool8 GeneratedMap_StageSharedTerrain(const u8 *patch, u32 size);
bool8 GeneratedMap_ApplySharedTerrain(const u8 *patch, u32 size);
bool8 GeneratedMap_StageCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_StageSharedCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_MatchesPreparedCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_StageSharedGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_MatchesPreparedGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
bool8 GeneratedMap_StageSharedWildsTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_MatchesPreparedWilds(const u8 *cells, u32 size);
bool8 GeneratedMap_StageSharedLargeTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_MatchesPreparedLarge(const u8 *cells, u32 size);
bool8 GeneratedMap_MatchesPreparedLargeWildlife(const u8 *cells, u32 size, u8 profile, const u8 *data, u32 dataSize);
bool8 GeneratedMap_SetEncounterProfile(u8 profile);
bool8 GeneratedMap_SetSharedEncounterProfile(u8 profile);
bool8 GeneratedMap_MatchesPreparedProfile(const u8 *cells, u32 size, u8 profile);
u8 GeneratedMap_EncounterProfile(void);
bool8 GeneratedMap_ValidateWildlife(const u8 *data, u32 size);
bool8 GeneratedMap_SetWildlife(const u8 *data, u32 size);
bool8 GeneratedMap_SetSharedWildlife(const u8 *data, u32 size);
bool8 GeneratedMap_MatchesPreparedWildlife(const u8 *cells, u32 size, u8 profile, const u8 *data, u32 dataSize);
const struct WildPokemonInfo *GeneratedMap_Wildlife(void);
/* Reload an optional offline template immediately before entry. */
bool8 Platform_ReloadGeneratedMap(void);
bool8 GeneratedMap_IsInside(void);
bool8 GeneratedMap_EntryPending(void);
bool8 GeneratedMap_MatchesPrepared(const u8 *cells, u32 size);
bool8 GeneratedMap_SharedCoordValid(unsigned x, unsigned y);
bool8 GeneratedMap_CanEnter(void);
bool8 GeneratedMap_Enter(void);
bool8 GeneratedMap_Leave(void);
const struct MapLayout *GeneratedMap_ResolveLayout(const struct MapLayout *base);
#endif
#endif
