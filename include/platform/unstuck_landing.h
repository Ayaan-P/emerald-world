#ifndef GUARD_PLATFORM_UNSTUCK_LANDING_H
#define GUARD_PLATFORM_UNSTUCK_LANDING_H
#if defined(PORTABLE) && !defined(_WIN32)
#include "gba/types.h"
/* Pure geometry helper. The caller must supply up-to-date plain-ground and
 * occupancy grids, exclude the player, and revalidate after arrival. */
bool8 Unstuck_SelectLanding(const u8 *plain, const u8 *clear, unsigned width, unsigned height,
                            unsigned spawnX, unsigned spawnY, s16 *outX, s16 *outY);
#endif
#endif
