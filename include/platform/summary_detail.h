#ifndef GUARD_PLATFORM_SUMMARY_DETAIL_H
#define GUARD_PLATFORM_SUMMARY_DETAIL_H
#ifdef PORTABLE
#include "constants/pokemon.h"

/* STAT_* order is HP, Attack, Defense, Speed, Sp. Atk, Sp. Def.
 * Mirror Cmd_hiddenpowercalc without touching battle state. */
static inline void SummaryDetail_CalculateHiddenPower(const u8 ivs[6], u8 *type, u8 *power)
{
    u8 i;
    u8 typeBits = 0;
    u8 powerBits = 0;

    for (i = 0; i < 6; i++)
    {
        typeBits |= (ivs[i] & 1) << i;
        powerBits |= ((ivs[i] & 2) >> 1) << i;
    }
    *power = (40 * powerBits) / 63 + 30;
    /* Hidden Power excludes Normal, Mystery and Fairy regardless of table size. */
    *type = ((TYPE_DARK - 2) * typeBits) / 63 + 1;
    if (*type >= TYPE_MYSTERY)
        (*type)++;
}
#endif
#endif
