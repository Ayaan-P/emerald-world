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

#ifdef PORTABLE
struct MapLayout;
struct WildPokemonInfo;
#define GENERATED_WILDLIFE_BYTES 37
#define GENERATED_MAP_TEMPLATE_BYTES (31 * 31)
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES (63 * 63)
#define GENERATED_GUIDE_BYTES 59
bool8 GeneratedMap_StageTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_StageLargeTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_StageWildsTemplate(const u8 *cells, u32 size);
bool8 GeneratedMap_StageGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size);
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
