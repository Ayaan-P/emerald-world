#ifndef GUARD_PLATFORM_WORLD_UNSTUCK_H
#define GUARD_PLATFORM_WORLD_UNSTUCK_H
#if defined(PORTABLE) && !defined(_WIN32)
#include "gba/types.h"
struct WarpData;
/* Returns a whitelist-backed last-heal destination or zero. This does not
 * perform a warp or establish that the destination is currently unoccupied. */
unsigned WorldUnstuck_HealDestination(const struct WarpData *warp, u8 playerGender);
/* Conservative: uncertain movement cases do not qualify for a cooldown waiver. */
bool8 WorldUnstuck_ConservativelyBoxed(void);
/* Must be checked again at confirmation and immediately before departure. */
bool8 WorldUnstuck_AllowedDeparture(void);
bool8 WorldUnstuck_StoryAllowsDestination(unsigned healId);
/* Snapshot of the currently loaded map only. It cannot establish whether
 * remote occupancy is fresh; callers must additionally establish freshness. */
bool8 WorldUnstuck_BuildLoadedGrid(u8 *plain, u8 *clear, unsigned capacity);
#endif
#endif
