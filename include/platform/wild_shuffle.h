#ifndef GUARD_PLATFORM_WILD_SHUFFLE_H
#define GUARD_PLATFORM_WILD_SHUFFLE_H
#ifdef PORTABLE
#include "gba/types.h"
/* Session-only opt-in. Seeds 1..20 are stable presets shared across engines. */
int WildShuffle_Enabled(void);
unsigned WildShuffle_Seed(void);
void WildShuffle_Toggle(void);
void WildShuffle_NextSeed(void);
u16 WildShuffle_MapNational(u16 national);
u16 WildShuffle_MapSpecies(u16 species);
#endif
#endif
