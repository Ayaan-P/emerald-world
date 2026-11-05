#ifndef GUARD_PLATFORM_GENERATED_MAP_H
#define GUARD_PLATFORM_GENERATED_MAP_H

/* Experimental local instance. Never enable without native acceptance. */
#ifndef GENERATED_MAP_READY
#define GENERATED_MAP_READY 0
#endif

#ifdef PORTABLE
struct MapLayout;
#define GENERATED_MAP_TEMPLATE_BYTES (31 * 31)
bool8 GeneratedMap_StageTemplate(const u8 *cells, u32 size);
/* Reload an optional offline template immediately before entry. */
bool8 Platform_ReloadGeneratedMap(void);
bool8 GeneratedMap_IsInside(void);
bool8 GeneratedMap_CanEnter(void);
bool8 GeneratedMap_Enter(void);
bool8 GeneratedMap_Leave(void);
const struct MapLayout *GeneratedMap_ResolveLayout(const struct MapLayout *base);
#endif
#endif
