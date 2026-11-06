#ifndef GUARD_PLATFORM_EXPANDED_ABILITIES_H
#define GUARD_PLATFORM_EXPANDED_ABILITIES_H
#ifdef PORTABLE
#include "gba/types.h"

/* Shared live/AI hook: resolved power, after dynamic power selection and before
 * field sports, attack/defense division and the damage formula's +2.
 * Never call for confusion self damage or fixed-damage script effects. */
u32 ExpandedAbilities_ModifyBasePower(u8 ability, u16 move, u32 resolvedPower);

/* Replaces, does not follow, the existing STAB multiply in Cmd_typecalc and
 * TypeCalc. Pass the resolved move type and the current battle types, not the
 * species types. This leaves the type-effectiveness table after STAB. */
s32 ExpandedAbilities_ApplyStab(s32 damage, u8 ability, u16 move, u8 moveType, u8 type1, u8 type2);

/* Only the AI's two 40-damage type-effectiveness probes, NOT damage scoring.
 * Call after TypeCalc and before the legacy 120/240/30/15 normalization. */
s32 ExpandedAbilities_NormalizeAiEffectiveness(s32 value, u8 ability, u16 move, u8 moveType, u8 type1, u8 type2);

/* Donor bb3fd057 IDs. FALSE means unsupported; output remains untouched.
 * Donor 76 is Air Lock, not native Cacophony. Do not truncate donor IDs. */
bool8 ExpandedAbilities_FromExpansion(u16 donorAbility, u8 *nativeAbility);

#endif
#endif
