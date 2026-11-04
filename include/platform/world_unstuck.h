#ifndef GUARD_PLATFORM_WORLD_UNSTUCK_H
#define GUARD_PLATFORM_WORLD_UNSTUCK_H
#if defined(PORTABLE) && !defined(_WIN32)
#include "gba/types.h"
struct WarpData;
struct MapHeader;
struct WorldUnstuckPlan {
    unsigned healId, originGroup, originNum, destinationGroup, destinationNum;
    s16 originX, originY, spawnX, spawnY, landingX, landingY;
};
enum WorldUnstuckPlanResult { UNSTUCK_PLAN_OK, UNSTUCK_PLAN_BLOCKED, UNSTUCK_PLAN_NO_HEAL, UNSTUCK_PLAN_NO_LANDING };
enum WorldUnstuckUseResult { UNSTUCK_USE_STARTED, UNSTUCK_USE_ONLINE_UNSUPPORTED, UNSTUCK_USE_BLOCKED, UNSTUCK_USE_COOLDOWN, UNSTUCK_USE_STORAGE_ERROR };
/* Returns a whitelist-backed last-heal destination or zero. This does not
 * perform a warp or establish that the destination is currently unoccupied. */
unsigned WorldUnstuck_HealDestination(const struct WarpData *warp, u8 playerGender);
/* Conservative: uncertain movement cases do not qualify for a cooldown waiver. */
bool8 WorldUnstuck_ConservativelyBoxed(void);
/* Must be checked again at confirmation and immediately before departure. */
bool8 WorldUnstuck_AllowedDeparture(void);
bool8 WorldUnstuck_StoryAllowsDestination(unsigned healId);
/* Computes a conservative proposal only. It does not reserve cooldown, warp,
 * alter save data or establish fresh remote occupancy. */
enum WorldUnstuckPlanResult WorldUnstuck_Plan(struct WorldUnstuckPlan *out);
/* No controls may be released on this result alone: online callers must prove
 * complete, fresh remote occupancy independently and pass TRUE only then. */
bool8 WorldUnstuck_RevalidateArrival(const struct WorldUnstuckPlan *plan, bool8 occupancyComplete);
/* Offline prototype only. A successful start owns a native Teleport effect. */
enum WorldUnstuckUseResult WorldUnstuck_Begin(void);
/* Platform statics survive soft reset; clear any in-flight action explicitly. */
void WorldUnstuck_Reset(void);
bool8 WorldUnstuck_SetPlannedWarp(void);
/* Returns TRUE only when an invalid arrival must return to its saved origin. */
bool8 WorldUnstuck_CompleteArrival(void);
/* Snapshot of the currently loaded map only. It cannot establish whether
 * remote occupancy is fresh; callers must additionally establish freshness. */
bool8 WorldUnstuck_BuildLoadedGrid(u8 *plain, u8 *clear, unsigned capacity);
/* Baseline geometry only. Dynamic tiles and live occupancy require a fresh
 * post-load check; callers must use the validated heal map and revalidate. */
bool8 WorldUnstuck_BuildStaticGrid(unsigned group, unsigned num, const struct MapHeader *map,
                                   u8 *plain, unsigned capacity);
#endif
#endif
