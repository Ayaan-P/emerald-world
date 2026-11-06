#ifdef PORTABLE
#include "global.h"
#include "battle.h"
#include "battle_anim.h"
#include "battle_controllers.h"
#include "pokemon.h"
#include "item.h"
#include "event_data.h"
#include "constants/flags.h"
#include "platform/world_rules.h"
#include "constants/items.h"
#include "constants/abilities.h"
#include "constants/pokemon.h"
#include "platform/native_link.h"
#include "platform/mega_battle.h"
#include "platform/mega_game.h"
#include <string.h>

static struct MegaBattleState sMega;
static u8 sQueued[MAX_BATTLERS_COUNT];
static u8 sSelected[MAX_BATTLERS_COUNT];

static bool8 MegaGame_FormCompatible(const struct MegaFormData *data)
{
    if (!data) return FALSE;
    /* Mega availability does not enable the modern ability/type engine. */
    if (data->ability == ABILITY_TECHNICIAN || data->ability == ABILITY_ADAPTABILITY
     || data->ability == ABILITY_TOUGH_CLAWS
     || data->type1 == TYPE_FAIRY || data->type2 == TYPE_FAIRY)
        return WorldRules_Enabled(WORLD_RULE_MODERN_SPLIT);
    return TRUE;
}

void MegaGame_CheckAcquisition(void)
{
    /* Steven's collection becomes available after the Mind Badge. This is
     * private story progression, not ownership of the world's ruleset. */
    gSpecialVar_Result = MEGA_FEATURE_READY
        && WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION) && FlagGet(FLAG_BADGE07_GET);
}

void MegaGame_Reset(void)
{
    MegaBattle_Reset(&sMega);
    memset(sQueued, 0, sizeof(sQueued));
    memset(sSelected, 0, sizeof(sSelected));
}

static bool8 MegaGame_Identity(u8 battler, u8 *owner, u8 *slot, struct Pokemon **mon)
{
    u16 index;
    if (battler >= gBattlersCount || battler >= MAX_BATTLERS_COUNT)
        return FALSE;
    index = gBattlerPartyIndexes[battler];
    if (index >= PARTY_SIZE) return FALSE;
    *owner = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? GetBattlerPosition(battler) : GetBattlerSide(battler);
    *slot = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? index % MULTI_PARTY_SIZE : index;
    if (*owner >= MEGA_TRAINERS) return FALSE;
    *mon = GetBattlerSide(battler) == B_SIDE_PLAYER ? &gPlayerParty[index] : &gEnemyParty[index];
    return TRUE;
}

bool8 MegaGame_CanQueue(u8 battler)
{
    struct Pokemon *mon;
    u8 owner, slot, i, stone;
    if (!MEGA_FEATURE_READY || !WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION)
     || !MegaGame_Identity(battler, &owner, &slot, &mon)) return FALSE;
    if ((gBattleTypeFlags & BATTLE_TYPE_LINK) && !NativeLink_IsActive()) return FALSE;
    if (gBattleTypeFlags & (BATTLE_TYPE_FRONTIER | BATTLE_TYPE_SAFARI | BATTLE_TYPE_WALLY_TUTORIAL | BATTLE_TYPE_TRAINER_HILL)) return FALSE;
    if (!(gBattleTypeFlags & BATTLE_TYPE_LINK)
     && (GetBattlerSide(battler) != B_SIDE_PLAYER || !CheckBagHasItem(ITEM_MEGA_RING, 1))) return FALSE;
    if ((gBattleTypeFlags & (BATTLE_TYPE_RECORDED | BATTLE_TYPE_RECORDED_LINK)) || !gBattleMons[battler].hp
     || (gBattleMons[battler].status2 & STATUS2_TRANSFORMED) || sMega.used[owner]
     || sMega.forms[owner][slot]) return FALSE;
    stone = MegaStone_FromItem(gBattleMons[battler].item);
    if (!MegaGame_FormCompatible(MegaForm_Get(MegaForm_Find(gBattleMons[battler].species, stone)))
     || GetMonData(mon, MON_DATA_SPECIES) != gBattleMons[battler].species) return FALSE;
    for (i = 0; i < gBattlersCount && i < MAX_BATTLERS_COUNT; i++)
    {
        u8 otherOwner, otherSlot; struct Pokemon *otherMon;
        if (i != battler && sQueued[i] && MegaGame_Identity(i, &otherOwner, &otherSlot, &otherMon)
         && otherOwner == owner) return FALSE;
    }
    return TRUE;
}

bool8 MegaGame_CanSelect(u8 battler)
{
    /* The owner controller may not have authoritative battle-mon data. */
    return MEGA_FEATURE_READY && battler < gBattlersCount && battler < MAX_BATTLERS_COUNT
        && WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION) && GetBattlerSide(battler) == B_SIDE_PLAYER
        && gBattleBufferA[battler][0] == CONTROLLER_CHOOSEMOVE
        && (gBattleBufferA[battler][3] & MEGA_MOVE_CAN_SELECT_BIT)
        && CheckBagHasItem(ITEM_MEGA_RING, 1);
}

bool8 MegaGame_ReplyAllowed(u8 battler, u8 announced)
{
    if (!MEGA_FEATURE_READY || battler >= gBattlersCount || battler >= MAX_BATTLERS_COUNT
     || announced != MEGA_MOVE_CAN_SELECT_BIT
     || !WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION)) return FALSE;
    if ((gBattleTypeFlags & BATTLE_TYPE_LINK) && !(gBattleTypeFlags & BATTLE_TYPE_IS_MASTER))
        return TRUE;
    return MegaGame_CanQueue(battler);
}

bool8 MegaGame_ValidateMoveChoice(u8 battler, u8 choice, u8 target)
{
    return battler < gBattlersCount && battler < MAX_BATTLERS_COUNT
        && (choice & ~MEGA_MOVE_CHOICE_BIT) < MAX_MON_MOVES
        && target < gBattlersCount && target < MAX_BATTLERS_COUNT
        && (!(choice & MEGA_MOVE_CHOICE_BIT) || MegaGame_CanQueue(battler));
}

bool8 MegaGame_ToggleSelection(u8 battler)
{
    u8 owner, slot, i; struct Pokemon *mon;
    if (battler >= MAX_BATTLERS_COUNT) return FALSE;
    if (sSelected[battler]) { sSelected[battler] = FALSE; return TRUE; }
    if (!MegaGame_CanSelect(battler) || !MegaGame_Identity(battler, &owner, &slot, &mon)) return FALSE;
    for (i = 0; i < gBattlersCount && i < MAX_BATTLERS_COUNT; i++)
    {
        u8 otherOwner, otherSlot; struct Pokemon *otherMon;
        if (i != battler && sSelected[i] && MegaGame_Identity(i, &otherOwner, &otherSlot, &otherMon)
         && owner == otherOwner) return FALSE;
    }
    sSelected[battler] = TRUE;
    return TRUE;
}

u8 MegaGame_ChoiceBit(u8 battler)
{
    return battler < MAX_BATTLERS_COUNT && sSelected[battler] && MegaGame_CanSelect(battler)
        ? MEGA_MOVE_CHOICE_BIT : 0;
}

void MegaGame_ClearSelection(u8 battler)
{
    if (battler < MAX_BATTLERS_COUNT) sSelected[battler] = FALSE;
}

bool8 MegaGame_Queue(u8 battler)
{
    if (!MegaGame_CanQueue(battler)) return FALSE;
    sQueued[battler] = TRUE;
    return TRUE;
}

void MegaGame_CancelQueue(u8 battler)
{
    if (battler < MAX_BATTLERS_COUNT) sQueued[battler] = FALSE;
}

static void MegaGame_WriteStats(u8 battler, const struct MegaBattleStats *stats)
{
    /* HP, stages, PP and statuses belong to the existing battle engine. */
    gBattleMons[battler].attack = stats->attack;
    gBattleMons[battler].defense = stats->defense;
    gBattleMons[battler].speed = stats->speed;
    gBattleMons[battler].spAttack = stats->spAttack;
    gBattleMons[battler].spDefense = stats->spDefense;
    gBattleMons[battler].types[0] = stats->type1;
    gBattleMons[battler].types[1] = stats->type2;
    gBattleMons[battler].ability = stats->ability;
}

void MegaGame_Restore(u8 battler)
{
    static const u8 ivFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_IV, MON_DATA_DEF_IV, MON_DATA_SPEED_IV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_IV};
    static const u8 evFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_EV, MON_DATA_DEF_EV, MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV};
    struct MegaStatInput input = {0};
    struct MegaBattleStats stats;
    struct Pokemon *mon;
    u8 owner, slot, i, form = MegaGame_ActiveForm(battler);
    if (!form || !MegaGame_Identity(battler, &owner, &slot, &mon)
     || gBattleMons[battler].species != GetMonData(mon, MON_DATA_SPECIES)) return;
    input.level = gBattleMons[battler].level;
    input.nature = GetNature(mon);
    for (i = 0; i < MEGA_STAT_COUNT; i++)
    {
        input.iv[i] = GetMonData(mon, ivFields[i]);
        input.ev[i] = GetMonData(mon, evFields[i]);
    }
    if (MegaForm_Calculate(form, &input, ModifyStatByNature, &stats))
        MegaGame_WriteStats(battler, &stats);
}

void MegaGame_RecalculateStats(u8 battler)
{
    u8 ability, type1, type2;
    if (battler >= gBattlersCount || battler >= MAX_BATTLERS_COUNT) return;
    /* EXP stat copies must not undo Skill Swap, Trace or changed types. */
    ability = gBattleMons[battler].ability;
    type1 = gBattleMons[battler].types[0];
    type2 = gBattleMons[battler].types[1];
    MegaGame_Restore(battler);
    gBattleMons[battler].ability = ability;
    gBattleMons[battler].types[0] = type1;
    gBattleMons[battler].types[1] = type2;
}

bool8 MegaGame_Apply(u8 battler)
{
    static const u8 ivFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_IV, MON_DATA_DEF_IV, MON_DATA_SPEED_IV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_IV};
    static const u8 evFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_EV, MON_DATA_DEF_EV, MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV};
    struct MegaStatInput input = {0};
    struct MegaBattleStats stats;
    struct Pokemon *mon;
    u8 owner, slot, stone, form, i;
    if (battler >= MAX_BATTLERS_COUNT || !sQueued[battler]) return FALSE;
    sQueued[battler] = FALSE;
    if (!MegaGame_CanQueue(battler) || !MegaGame_Identity(battler, &owner, &slot, &mon)) return FALSE;
    input.level = gBattleMons[battler].level;
    input.nature = GetNature(mon);
    for (i = 0; i < MEGA_STAT_COUNT; i++)
    {
        input.iv[i] = GetMonData(mon, ivFields[i]);
        input.ev[i] = GetMonData(mon, evFields[i]);
    }
    stone = MegaStone_FromItem(gBattleMons[battler].item);
    form = MegaBattle_Transform(&sMega, owner, slot, gBattleMons[battler].species,
        stone, TRUE, gBattleMons[battler].hp != 0, &input, ModifyStatByNature, &stats);
    if (!form) return FALSE;
    /* Never write a Mega species or altered stats into either trainer's party. */
    MegaGame_WriteStats(battler, &stats);
    return TRUE;
}

bool8 MegaGame_OnSwitchIn(u8 battler)
{
    if (battler >= gBattlersCount || battler >= MAX_BATTLERS_COUNT) return FALSE;
    MegaGame_CancelQueue(battler);
    MegaGame_ClearSelection(battler);
    if (!MEGA_FEATURE_READY || !WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION)
     || !MegaGame_ActiveForm(battler)) return FALSE;
    MegaGame_Restore(battler);
    return TRUE;
}

/* Dot's versioned event carries trainer-local identity, never party data. */
bool8 MegaGame_ObserveForm(u8 battler, u8 form, u8 partyIndex)
{
    struct Pokemon *mon;
    const struct MegaFormData *data;
    u8 owner, slot;
    if (!MEGA_FEATURE_READY || !WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION)
     || battler >= gBattlersCount || battler >= MAX_BATTLERS_COUNT
     || partyIndex >= PARTY_SIZE) return FALSE;
    owner = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? GetBattlerPosition(battler) : GetBattlerSide(battler);
    if (owner >= MEGA_TRAINERS) return FALSE;
    if ((gBattleTypeFlags & BATTLE_TYPE_MULTI)
     && partyIndex / MULTI_PARTY_SIZE != (GetBattlerPosition(battler) >> 1)) return FALSE;
    slot = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? partyIndex % MULTI_PARTY_SIZE : partyIndex;
    mon = GetBattlerSide(battler) == B_SIDE_PLAYER ? &gPlayerParty[partyIndex] : &gEnemyParty[partyIndex];
    data = MegaForm_Get(form);
    if (!MegaGame_FormCompatible(data) || GetMonData(mon, MON_DATA_SPECIES) != data->baseSpecies) return FALSE;
    if (sMega.used[owner] && sMega.forms[owner][slot] != form) return FALSE;
    sMega.used[owner] = TRUE;
    sMega.forms[owner][slot] = form;
    return TRUE;
}

u8 MegaGame_ActiveForm(u8 battler)
{
    struct Pokemon *mon;
    const struct MegaFormData *data;
    u8 owner, slot, form;
    if (!MegaGame_Identity(battler, &owner, &slot, &mon)) return MEGA_FORM_NONE;
    form = MegaBattle_GetForm(&sMega, owner, slot);
    data = MegaForm_Get(form);
    return MegaGame_FormCompatible(data) && data->baseSpecies == GetMonData(mon, MON_DATA_SPECIES) ? form : MEGA_FORM_NONE;
}
#endif
