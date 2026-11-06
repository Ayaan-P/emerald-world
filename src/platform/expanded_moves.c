#ifdef PORTABLE
#include "gba/types.h"
#include "constants/global.h"
#include "constants/pokemon.h"
#include "constants/battle.h"
#include "platform/expanded_moves.h"
#include "platform/native_link.h"
#include "platform/world_rules.h"

extern u32 gBattleTypeFlags;
extern const u8 gTypeEffectiveness[336];
#define TYPE_FORESIGHT 0xFE
#define TYPE_ENDTABLE 0xFF

static const u8 sExpandedMoveCategory[MOVES_COUNT - EXPANDED_MOVES_START] =
{
#include "../data/expanded_moves/categories.h"
};

static const u8 sModernTypeEffectiveness[] =
{
#include "../data/expanded_moves/type_chart.h"
};

typedef char ExpandedMovesFitNativeLearnsets[(MOVES_COUNT <= 512) ? 1 : -1];
typedef char ExpandedMoveCategoriesComplete[(sizeof(sExpandedMoveCategory) == MOVES_COUNT - EXPANDED_MOVES_START) ? 1 : -1];

u8 ExpandedMoves_Category(u16 move)
{
    if (move < EXPANDED_MOVES_START || move >= MOVES_COUNT)
        return EXPANDED_CATEGORY_INVALID;
    return sExpandedMoveCategory[move - EXPANDED_MOVES_START];
}

bool8 ExpandedMoves_IsSupported(u16 move)
{
    return move != MOVE_NONE && move < MOVES_COUNT;
}

bool8 ExpandedMoves_UseModernTypes(void)
{
    /* Same compatibility boundary as BattleRules_UseModernSplit. No saves,
     * legacy link partners, or recorded battles are silently reinterpreted. */
    return WorldRules_Enabled(WORLD_RULE_MODERN_SPLIT)
        && !(gBattleTypeFlags & (BATTLE_TYPE_RECORDED | BATTLE_TYPE_RECORDED_LINK))
        && (!(gBattleTypeFlags & BATTLE_TYPE_LINK) || NativeLink_IsActive());
}

const u8 *ExpandedMoves_TypeTable(void)
{
    return ExpandedMoves_UseModernTypes() ? sModernTypeEffectiveness : gTypeEffectiveness;
}

u16 ExpandedMoves_TypeTableSize(void)
{
    return ExpandedMoves_UseModernTypes() ? sizeof(sModernTypeEffectiveness) : sizeof(gTypeEffectiveness);
}

u16 ExpandedMoves_PlayableCount(void)
{
    return ExpandedMoves_UseModernTypes() ? MOVES_COUNT : EXPANDED_MOVES_START;
}
#endif
