#ifdef PORTABLE
/* Repel-only adaptation of RHH's pokeemerald-expansion src/sprays.c,
 * c460a8661dfa0598ae25d42a968c690ecbf489c6, based on pret/pokeemerald.
 * See upstream README.md and CREDITS.md for contributor credits. This is not
 * a new licensing grant. Enumeration/menu flow is retained; native item IDs,
 * script ownership and transactional consumption are platform adapters. */
#include "global.h"
#include "battle_pike.h"
#include "battle_pyramid.h"
#include "event_data.h"
#include "field_specials.h"
#include "item.h"
#include "link.h"
#include "main.h"
#include "menu.h"
#include "overworld.h"
#include "palette.h"
#include "script.h"
#include "script_menu.h"
#include "strings.h"
#include "platform/native_link.h"
#include "platform/repeat_repel.h"
#include "platform/world_activity.h"
#include "platform/world_coop.h"
#include "constants/battle_pyramid.h"
#include "constants/flags.h"
#include "constants/vars.h"

extern const u8 RepeatRepel_AfterBegin[];
extern const u8 RepeatRepel_AfterDraw[];
extern const u8 RepeatRepel_AfterCommit[];

/* Stock IDs are Repel=86, Super=83, Max=84, not Expansion's contiguous IDs. */
static const u16 sRepels[] = {ITEM_REPEL, ITEM_SUPER_REPEL, ITEM_MAX_REPEL};
static struct
{
    bool8 active;
    u8 count;
    u16 items[ARRAY_COUNT(sRepels)];
    struct SaveBlock1 *save1;
    struct SaveBlock2 *save2;
    struct WarpData location;
} sRepeatRepel;

static bool8 FieldIsSafe(void)
{
    /* Our own expiry script locks controls. Rejecting every enabled script
     * would reject the genuine interaction; exact script operands identify it. */
    return gSaveBlock1Ptr != NULL && gSaveBlock2Ptr != NULL
        && gMain.callback2 == CB2_Overworld && !gMain.inBattle
        && !gPaletteFade.active && ArePlayerFieldControlsLocked()
        && GetTaskCount() < NUM_TASKS
        && !gWirelessCommType && !gReceivedRemoteLinkPlayers
        && !IsOverworldLinkActive() && !NativeLink_IsActive()
        && !WorldCoop_IsBattle() && !WorldCoop_IsPrivateRewards()
        && !WorldActivity_OwnsFieldInput() && !WorldActivity_IsEncounterPending()
        && !InUnionRoom() && !InMultiPartnerRoom() && !InBattlePike()
        && CurrentBattlePyramidLocation() == PYRAMID_LOCATION_NONE
        && !FlagGet(FLAG_STORING_ITEMS_IN_PYRAMID_BAG)
        && VarGet(VAR_REPEL_STEP_COUNT) == 0;
}

/* Expansion CountOrGetSprays, specialized to existing owned Repels only.
 * Snapshot the offered identities, never infer a selection by live bag order. */
static u8 CountOrGetSprays(u16 *items)
{
    u8 i, count = 0;
    for (i = 0; i < ARRAY_COUNT(sRepels); i++)
        if (CheckBagHasItem(sRepels[i], 1))
            items[count++] = sRepels[i];
    return count;
}

static bool8 FlowIsSafe(const u8 *scriptPtr)
{
    return sRepeatRepel.active && ScriptContext_IsAt(scriptPtr) && FieldIsSafe()
        && gSaveBlock1Ptr == sRepeatRepel.save1
        && gSaveBlock2Ptr == sRepeatRepel.save2
        && gSaveBlock1Ptr->location.mapGroup == sRepeatRepel.location.mapGroup
        && gSaveBlock1Ptr->location.mapNum == sRepeatRepel.location.mapNum;
}

void RepeatRepel_Begin(void)
{
    sRepeatRepel.active = FALSE;
    sRepeatRepel.count = 0;
    gSpecialVar_Result = 0;
    if (!ScriptContext_IsAt(RepeatRepel_AfterBegin) || !FieldIsSafe())
        return;
    sRepeatRepel.save1 = gSaveBlock1Ptr;
    sRepeatRepel.save2 = gSaveBlock2Ptr;
    sRepeatRepel.location = gSaveBlock1Ptr->location;
    sRepeatRepel.count = CountOrGetSprays(sRepeatRepel.items);
    sRepeatRepel.active = sRepeatRepel.count != 0;
    gSpecialVar_Result = sRepeatRepel.count;
    /* GetSprayId in the no-persistent-last-item branch returns the first owned
     * strength. Script buffers this name for the single-strength yes/no. */
    if (sRepeatRepel.active)
        gSpecialVar_0x8004 = sRepeatRepel.items[0];
}

void RepeatRepel_DrawMenu(void)
{
    struct MenuAction menuItems[ARRAY_COUNT(sRepels) + 1] = {0};
    u8 i;
    gSpecialVar_Result = FALSE;
    if (!FlowIsSafe(RepeatRepel_AfterDraw))
        return;
    /* Printing the expiry text can yield frames. Offer only still-owned items. */
    sRepeatRepel.count = CountOrGetSprays(sRepeatRepel.items);
    if (sRepeatRepel.count == 0)
        return;
    for (i = 0; i < sRepeatRepel.count; i++)
        menuItems[i].text = GetItemName(sRepeatRepel.items[i]);
    menuItems[sRepeatRepel.count].text = gText_Cancel2;
    /* Expansion DrawSprayMenu layout, native input/cleanup task. The actions
     * are printed synchronously, so no task stores a stack pointer. */
    gSpecialVar_Result = ScriptMenu_DrawRepelChoice(18,
        10 - 2 * sRepeatRepel.count, menuItems, sRepeatRepel.count + 1);
}

void RepeatRepel_Commit(void)
{
    u16 selection = gSpecialVar_Result;
    u16 item = ITEM_NONE, steps = 0;
    u8 i;
    bool8 valid = FlowIsSafe(RepeatRepel_AfterCommit);
    /* One-shot even on failure. Cancel/out-of-range cannot become an item ID. */
    sRepeatRepel.active = FALSE;
    gSpecialVar_Result = FALSE;
    if (!valid || selection >= sRepeatRepel.count)
        return;
    item = sRepeatRepel.items[selection];
    for (i = 0; i < ARRAY_COUNT(sRepels); i++)
        if (item == sRepels[i])
            steps = GetItemHoldEffectParam(item);
    if (!steps || !CheckBagHasItem(item, 1) || !RemoveBagItem(item, 1))
        return;
    /* No yields/callbacks between revalidation, successful removal and write. */
    VarSet(VAR_REPEL_STEP_COUNT, steps);
    gSpecialVar_0x8004 = item;
    gSpecialVar_Result = TRUE;
}

void RepeatRepel_End(void)
{
    sRepeatRepel.active = FALSE;
    sRepeatRepel.count = 0;
}
#endif
