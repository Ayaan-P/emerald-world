#ifndef GUARD_PLATFORM_EXPANDED_MOVES_H
#define GUARD_PLATFORM_EXPANDED_MOVES_H
#ifdef PORTABLE
#include "gba/types.h"
#include "constants/moves.h"
#define EXPANDED_MOVES_START 355
#define EXPANDED_CATEGORY_PHYSICAL 0
#define EXPANDED_CATEGORY_SPECIAL 1
#define EXPANDED_CATEGORY_STATUS 2
#define EXPANDED_CATEGORY_INVALID 255
/* The helper deliberately returns INVALID for native entries. The existing
 * native-category table remains authoritative for IDs below 355. */
u8 ExpandedMoves_Category(u16 move);
bool8 ExpandedMoves_IsSupported(u16 move);
bool8 ExpandedMoves_UseModernTypes(void);
const u8 *ExpandedMoves_TypeTable(void);
u16 ExpandedMoves_TypeTableSize(void);
/* Count for random move selection: legacy games must not roll appended IDs. */
u16 ExpandedMoves_PlayableCount(void);
#endif
#endif
