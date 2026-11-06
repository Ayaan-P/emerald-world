#ifndef GUARD_PLATFORM_MODERN_SPECIES_TYPES_H
#define GUARD_PLATFORM_MODERN_SPECIES_TYPES_H
#ifdef PORTABLE
#include "gba/types.h"

/* Resolve base species types for runtime use, never saved Pokemon data.
 * typeIndex is one of the two species type slots (0 or 1). */
u8 ModernSpeciesTypes_GetType(u16 species, u8 typeIndex);
#endif
#endif
