#ifndef GUARD_PLATFORM_WORLD_TRAVEL_H
#define GUARD_PLATFORM_WORLD_TRAVEL_H
#ifdef PORTABLE
#include <stdio.h>
#include "gba/types.h"
/* Pause menu handoff. Update and raw-key consumption run after a committed
 * frame, while FilterInput only suppresses ordinary field actions. */
void WorldTravel_RequestMenu(void);
void WorldTravel_Update(void);
bool8 WorldTravel_OwnsFieldInput(void);
void WorldTravel_WriteJSON(FILE *file);
void WorldTravel_Close(void);
bool8 WorldTravel_CanAllocateFly(void);
/* Rally uses the ordinary field warp tasks, never writes save bytes. Only a
 * checked ordinary floor (including saved elevation) is an admissible anchor. */
bool8 WorldTravel_RallyTileSafe(unsigned group, unsigned num, s16 x, s16 y, unsigned elevation, bool8 online);
bool8 WorldTravel_RallyWarp(unsigned group, unsigned num, s16 x, s16 y, unsigned elevation, bool8 online);
bool8 WorldTravel_NativeFlyRunning(void);
/* Called at the end of native Fly-in, before releasing controls. Zero means
 * the arrival is valid or not ours. Otherwise use this ordinary heal landing. */
unsigned WorldTravel_ArrivalFallback(void);
/* Checked main-thread request into Emerald's existing Fly effect tasks. */
bool8 WorldTravel_StartNativeFly(unsigned group, unsigned num, s16 x, s16 y, unsigned mon);
#endif
#endif
