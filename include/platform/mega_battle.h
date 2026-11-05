#ifndef GUARD_PLATFORM_MEGA_BATTLE_H
#define GUARD_PLATFORM_MEGA_BATTLE_H

#include "platform/mega_forms.h"
#define MEGA_TRAINERS 4
#define MEGA_PARTY_SLOTS 6
#define MEGA_STAT_COUNT 5

/* One instance belongs to one battle. Slot numbers are trainer-local stable
 * slots supplied by the caller, never an opponent's temporary staged index. */
struct MegaBattleState {
    u8 used[MEGA_TRAINERS];
    u8 forms[MEGA_TRAINERS][MEGA_PARTY_SLOTS];
};
struct MegaStatInput {
    u8 level, nature;
    u8 iv[MEGA_STAT_COUNT], ev[MEGA_STAT_COUNT];
};
struct MegaBattleStats {
    u16 attack, defense, speed, spAttack, spDefense;
    u8 type1, type2, ability;
};
typedef u16 (*MegaNatureAdjust)(u8 nature, u16 stat, u8 statIndex);
void MegaBattle_Reset(struct MegaBattleState *state);
u8 MegaBattle_GetForm(const struct MegaBattleState *state, u8 owner, u8 slot);
bool8 MegaForm_Calculate(u8 form, const struct MegaStatInput *input,
                         MegaNatureAdjust nature, struct MegaBattleStats *result);
u8 MegaBattle_Transform(struct MegaBattleState *state, u8 owner, u8 slot,
                        u16 species, u8 stone, bool8 hasKey, bool8 conscious,
                        const struct MegaStatInput *input, MegaNatureAdjust nature,
                        struct MegaBattleStats *result);
#endif
