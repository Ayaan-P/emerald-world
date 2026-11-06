#ifndef GUARD_PLATFORM_EXPANDED_SPECIES_H
#define GUARD_PLATFORM_EXPANDED_SPECIES_H
#ifdef PORTABLE
#include "gba/types.h"
/* Pinned donor National range, not a claim that every entry is playable. */
#define EXPANDED_DEX_NATIONAL_MAX 1025
/* Validity is independent of acquisition policy: existing owned monsters survive
 * reconnect and Continue even when the current world disables new encounters. */
bool8 ExpandedSpecies_IsPlayable(u16 species);
u16 ExpandedSpecies_Clamp(u16 species);
u16 ExpandedSpecies_ClampIcon(u16 species);
u16 ExpandedSpecies_LegacyAnimSpecies(u16 species);
u16 ExpandedSpecies_NationalDexNumber(u16 species);
u16 ExpandedSpecies_FromNationalDexNumber(u16 dexNumber);
u16 ExpandedSpecies_ResolveEncounter(u16 species, u8 mapGroup, u8 mapNum);
/* SDL passes its canonical mounted save path, never a discovered HOME path.
 * The supplemental .expanded-dex sidecar supports frozen EDX1 import and
 * National-indexed EDX2 slots. No SaveBlock or vanilla Dex bit is repurposed.
 * Init(NULL, FALSE) is session-only and closes any previous sidecar.
 * Reset is safe on soft reset: rebind lazily after trainer save loading. */
void ExpandedDex_Init(const char *savePath, bool8 allowPersistence);
void ExpandedDex_Reset(void);
s8 ExpandedDex_GetSetFlag(u16 nationalDexNo, u8 caseID);
#endif
#endif
