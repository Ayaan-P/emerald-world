#ifdef PORTABLE
#include "global.h"
#include "battle.h"
#include "pokemon.h"
#include "battle_move_split.h"
#include "constants/abilities.h"
#include "platform/expanded_abilities.h"

/* Ported from Expansion bb3fd057: CalcMoveBasePowerAfterModifiers and
 * fpmath.h's uq4_12_multiply_by_int_half_down. Preserve Q4.12 rounding,
 * especially Tough Claws' 5325/4096 rather than a guessed integer 130/100. */
static u32 ApplyPowerModifier(u32 power, u32 modifier)
{
    return (power * modifier + 2047) / 4096;
}

u32 ExpandedAbilities_ModifyBasePower(u8 ability, u16 move, u32 resolvedPower)
{
    u8 type;

    if (!BattleRules_UseModernSplit() || move == MOVE_NONE || move >= MOVES_COUNT || resolvedPower == 0)
        return resolvedPower;
    type = gBattleMoves[move].type;
    if (!BattleMove_IsPhysical(move, type) && !BattleMove_IsSpecial(move, type))
        return resolvedPower;

    if (ability == ABILITY_TECHNICIAN && resolvedPower <= 60)
        return ApplyPowerModifier(resolvedPower, 6144);
    /* This bounded move set has no Shell Side Arm or Punching Glove. Its
     * contact predicate is the native move flag, never physical category.
     * Long Reach cannot coexist with the attacker's Tough Claws ability. */
    if (ability == ABILITY_TOUGH_CLAWS && (gBattleMoves[move].flags & FLAG_MAKES_CONTACT))
        return ApplyPowerModifier(resolvedPower, 5325);
    return resolvedPower;
}

s32 ExpandedAbilities_ApplyStab(s32 damage, u8 ability, u16 move, u8 moveType, u8 type1, u8 type2)
{
    bool8 modern = BattleRules_UseModernSplit();

    if (moveType != type1 && moveType != type2)
        return damage;
    if (modern && (moveType == TYPE_MYSTERY || move == MOVE_STRUGGLE))
        return damage;
    if (modern && ability == ABILITY_ADAPTABILITY)
        return damage * 2;
    return damage * 15 / 10;
}

s32 ExpandedAbilities_NormalizeAiEffectiveness(s32 value, u8 ability, u16 move, u8 moveType, u8 type1, u8 type2)
{
    /* The legacy AI strips 1.5x STAB with magic sentinel values. With 2x
     * Adaptability those sentinels collide with actual type multipliers.
     * Its probes start at exactly 40, so removing 2x here is lossless. */
    if (BattleRules_UseModernSplit() && ability == ABILITY_ADAPTABILITY
     && move != MOVE_STRUGGLE && moveType != TYPE_MYSTERY
     && (moveType == type1 || moveType == type2))
        return value / 2;
    return value;
}

bool8 ExpandedAbilities_FromExpansion(u16 donorAbility, u8 *nativeAbility)
{
    u8 result;

    if (nativeAbility == NULL)
        return FALSE;
    /* Only these donor slots are identical to the legacy namespace. The
     * donor removed Cacophony and reused native 77 for Tangled Feet. */
    if (donorAbility <= 75)
        result = donorAbility;
    else
    {
        switch (donorAbility)
        {
        case 76: result = ABILITY_AIR_LOCK; break;
        case 101: result = ABILITY_TECHNICIAN; break;
        case 91: result = ABILITY_ADAPTABILITY; break;
        case 181: result = ABILITY_TOUGH_CLAWS; break;
        default: return FALSE;
        }
    }
    *nativeAbility = result;
    return TRUE;
}
#endif
