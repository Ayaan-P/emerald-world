#ifdef PORTABLE
#include "global.h"
#include "battle.h"
#include "battle_anim.h"
#include "pokemon.h"
#include "item.h"
#include "event_data.h"
#include "constants/flags.h"
#include "constants/items.h"
#include "platform/native_link.h"
#include "platform/mega_battle.h"
#include "platform/mega_game.h"
#include <string.h>

static struct MegaBattleState sMega;
static u8 sQueued[MAX_BATTLERS_COUNT];
static u8 sSelected[MAX_BATTLERS_COUNT];
static u8 sActiveForm[MAX_BATTLERS_COUNT];
static u8 sActiveOwner[MAX_BATTLERS_COUNT], sActiveSlot[MAX_BATTLERS_COUNT];

void MegaGame_Reset(void)
{
    MegaBattle_Reset(&sMega);
    memset(sQueued, 0, sizeof(sQueued));
    memset(sSelected, 0, sizeof(sSelected));
    memset(sActiveForm, 0, sizeof(sActiveForm));
    memset(sActiveOwner, 0, sizeof(sActiveOwner));
    memset(sActiveSlot, 0, sizeof(sActiveSlot));
}

static bool8 MegaGame_Identity(u8 battler, u8 *owner, u8 *slot, struct Pokemon **mon)
{
    u8 index;
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
    if (!MEGA_FEATURE_READY || !FlagGet(FLAG_MEGA_EVOLUTION)
     || !MegaGame_Identity(battler, &owner, &slot, &mon)) return FALSE;
    if ((gBattleTypeFlags & BATTLE_TYPE_LINK) && !NativeLink_IsActive()) return FALSE;
    if ((gBattleTypeFlags & (BATTLE_TYPE_RECORDED | BATTLE_TYPE_RECORDED_LINK)) || !gBattleMons[battler].hp
     || (gBattleMons[battler].status2 & STATUS2_TRANSFORMED) || sMega.used[owner]
     || sMega.forms[owner][slot]) return FALSE;
    stone = MegaStone_FromItem(gBattleMons[battler].item);
    if (!MegaForm_Find(gBattleMons[battler].species, stone)
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
    return MegaGame_CanQueue(battler) && GetBattlerSide(battler) == B_SIDE_PLAYER
        && CheckBagHasItem(ITEM_MEGA_RING, 1);
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

/* Battle-party indices refer to stable underlying party slots; menu order is
 * a separate permutation. Never identify a form by nickname or personality. */
static bool8 MegaGame_CalculateStats(u8 battler, struct Pokemon *mon, u8 form,
                                    struct MegaBattleStats *stats)
{
    static const u8 ivFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_IV, MON_DATA_DEF_IV, MON_DATA_SPEED_IV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_IV};
    static const u8 evFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_EV, MON_DATA_DEF_EV, MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV};
    struct MegaStatInput input = {0};
    u8 i;
    input.level = gBattleMons[battler].level;
    input.nature = GetNature(mon);
    for (i = 0; i < MEGA_STAT_COUNT; i++)
    {
        input.iv[i] = GetMonData(mon, ivFields[i]);
        input.ev[i] = GetMonData(mon, evFields[i]);
    }
    return MegaForm_Calculate(form, &input, ModifyStatByNature, stats);
}

static void MegaGame_SetStats(u8 battler, const struct MegaBattleStats *stats, u8 form)
{
    /* Never write a Mega species or altered stats into either trainer's party. */
    gBattleMons[battler].attack = stats->attack; gBattleMons[battler].defense = stats->defense;
    gBattleMons[battler].speed = stats->speed; gBattleMons[battler].spAttack = stats->spAttack;
    gBattleMons[battler].spDefense = stats->spDefense; gBattleMons[battler].types[0] = stats->type1;
    gBattleMons[battler].types[1] = stats->type2; gBattleMons[battler].ability = stats->ability;
    sActiveForm[battler] = form;
    {
        u8 owner, slot; struct Pokemon *mon;
        if (MegaGame_Identity(battler, &owner, &slot, &mon))
        { sActiveOwner[battler] = owner; sActiveSlot[battler] = slot; }
    }
}

bool8 MegaGame_Apply(u8 battler)
{
    struct MegaBattleStats stats;
    struct MegaStatInput input = {0};
    struct Pokemon *mon;
    u8 owner, slot, stone, form, i;
    static const u8 ivFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_IV, MON_DATA_DEF_IV, MON_DATA_SPEED_IV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_IV};
    static const u8 evFields[MEGA_STAT_COUNT] = {MON_DATA_ATK_EV, MON_DATA_DEF_EV, MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV};
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
    MegaGame_SetStats(battler, &stats, form);
    return TRUE;
}

/* Called after new switch-in data has replaced the outgoing battle mon. */
bool8 MegaGame_OnSwitchIn(u8 battler)
{
    struct Pokemon *mon;
    struct MegaBattleStats stats;
    const struct MegaFormData *data;
    u8 owner, slot, form;
    if (battler >= MAX_BATTLERS_COUNT) return FALSE;
    sQueued[battler] = sSelected[battler] = sActiveForm[battler] = 0;
    if (!MEGA_FEATURE_READY || !MegaGame_Identity(battler, &owner, &slot, &mon)) return FALSE;
    form = MegaBattle_GetForm(&sMega, owner, slot);
    data = MegaForm_Get(form);
    if (!data || data->baseSpecies != gBattleMons[battler].species
     || data->baseSpecies != GetMonData(mon, MON_DATA_SPECIES)
     || !MegaGame_CalculateStats(battler, mon, form, &stats)) return FALSE;
    MegaGame_SetStats(battler, &stats, form);
    return TRUE;
}

/* Accept only an authoritative event matching the currently staged party
 * slot. This changes transient form identity, never the underlying party. */
bool8 MegaGame_ObserveForm(u8 battler, u8 form, u8 partyIndex)
{
    struct Pokemon *mon;
    const struct MegaFormData *data;
    u8 owner, slot;
    if (!MEGA_FEATURE_READY || battler >= gBattlersCount || battler >= MAX_BATTLERS_COUNT
     || partyIndex >= PARTY_SIZE) return FALSE;
    owner = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? GetBattlerPosition(battler) : GetBattlerSide(battler);
    if (owner >= MEGA_TRAINERS) return FALSE;
    if ((gBattleTypeFlags & BATTLE_TYPE_MULTI)
     && partyIndex / MULTI_PARTY_SIZE != (GetBattlerPosition(battler) >> 1)) return FALSE;
    slot = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? partyIndex % MULTI_PARTY_SIZE : partyIndex;
    mon = GetBattlerSide(battler) == B_SIDE_PLAYER ? &gPlayerParty[partyIndex] : &gEnemyParty[partyIndex];
    data = MegaForm_Get(form);
    if (!data || GetMonData(mon, MON_DATA_SPECIES) != data->baseSpecies) return FALSE;
    if (sMega.used[owner] && sMega.forms[owner][slot] != form) return FALSE;
    sMega.used[owner] = TRUE;
    sMega.forms[owner][slot] = form;
    sActiveForm[battler] = form; sActiveOwner[battler] = owner; sActiveSlot[battler] = slot;
    return TRUE;
}

u8 MegaGame_ActiveForm(u8 battler)
{
    struct Pokemon *mon;
    u8 owner, slot;
    if (battler >= MAX_BATTLERS_COUNT || !sActiveForm[battler]
     || !MegaGame_Identity(battler, &owner, &slot, &mon)
     || owner != sActiveOwner[battler] || slot != sActiveSlot[battler]) return MEGA_FORM_NONE;
    return sActiveForm[battler];
}
#endif
