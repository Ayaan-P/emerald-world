/* Exercise the real planner/transaction with explicit medicine/engine fixtures.
 * This is not evidence for stock item-effect or visible native UI acceptance. */
#include "../../src/platform/party_autoheal.c"
#undef NDEBUG
#include <assert.h>
#include <stdio.h>

struct Main gMain;
struct PaletteFadeControl gPaletteFade;
struct PartyMenu gPartyMenu;
struct Pokemon gPlayerParty[PARTY_SIZE];
u8 gPlayerPartyCount, gActiveBattler, gPotentialItemEffectBattler;
u8 gWirelessCommType, gReceivedRemoteLinkPlayers;
u32 gBattleTypeFlags;
static struct SaveBlock1 save1;
static struct SaveBlock2 save2;
struct SaveBlock1 *gSaveBlock1Ptr = &save1;
struct SaveBlock2 *gSaveBlock2Ptr = &save2;
static int busy, linked, coop, script, pyramid, failRemoval, removals;
static u16 secretFlags, secretItem;
void CB2_ReturnToFieldWithOpenMenu(void) {}
int NativeLink_IsActive(void) { return linked; }
int WorldCoop_IsBattle(void) { return coop; }
bool8 WorldCoop_IsPrivateRewards(void) { return FALSE; }
int WorldActivity_OwnsFieldInput(void) { return busy; }
int WorldActivity_IsEncounterPending(void) { return busy; }
bool8 ScriptContext_IsEnabled(void) { return script; }
bool32 InUnionRoom(void) { return FALSE; }
bool32 IsOverworldLinkActive(void) { return linked; }
bool8 InMultiPartnerRoom(void) { return FALSE; }
bool8 InBattlePike(void) { return FALSE; }
u8 CurrentBattlePyramidLocation(void) { return pyramid; }
bool8 FlagGet(u16 flag) { return FALSE; }
u16 VarGet(u16 var) { return var == VAR_SECRET_BASE_LOW_TV_FLAGS ? secretFlags : secretItem; }
u16 *GetVarPointer(u16 var) { return var == VAR_SECRET_BASE_LOW_TV_FLAGS ? &secretFlags : &secretItem; }
bool8 VarSet(u16 var, u16 value) { *GetVarPointer(var) = value; return TRUE; }
u32 GetMonData2(struct Pokemon *mon, s32 field)
{
    switch (field)
    {
    case MON_DATA_SPECIES: return mon->box.hasSpecies;
    case MON_DATA_IS_EGG: return mon->box.isEgg;
    case MON_DATA_HP: return mon->hp;
    case MON_DATA_MAX_HP: return mon->maxHP;
    case MON_DATA_STATUS: return mon->status;
    default: assert(0); return 0;
    }
}
u16 GetItemPrice(u16 item)
{
    if (item == ITEM_ORAN_BERRY) return 20;
    if (item == ITEM_POTION || item == ITEM_FRESH_WATER) return 300;
    if (item == ITEM_ANTIDOTE || item == ITEM_BURN_HEAL) return 100;
    if (item == ITEM_HEAL_POWDER) return 50;
    return 3000;
}
u16 CountTotalItemQuantityInBag(u16 item)
{
    for (unsigned i = 0; i < BAG_ITEMS_COUNT; i++)
        if (save1.bagPocket_Items[i].itemId == item) return save1.bagPocket_Items[i].quantity;
    return 0;
}
bool8 RemoveBagItem(u16 item, u16 count)
{
    if (++removals == failRemoval) return FALSE;
    for (unsigned i = 0; i < BAG_ITEMS_COUNT; i++)
        if (save1.bagPocket_Items[i].itemId == item && save1.bagPocket_Items[i].quantity >= count)
        { save1.bagPocket_Items[i].quantity -= count; return TRUE; }
    return FALSE;
}
bool8 PokemonUseItemEffects(struct Pokemon *mon, u16 item, u8 slot, u8 move, bool8 ai)
{
    for (unsigned i = 0; i < PARTY_SIZE; i++) assert(mon != &gPlayerParty[i]);
    assert(!ai && !move);
    gActiveBattler = 0;
    gPotentialItemEffectBattler = 9;
    /* Deliberate no-effect mutation catches accidental trial commits. */
    mon->box.markings++;
    if ((item == ITEM_POTION || item == ITEM_FRESH_WATER || item == ITEM_ORAN_BERRY) && mon->hp < mon->maxHP)
    { mon->hp += item == ITEM_POTION ? 20 : 10; if (mon->hp > mon->maxHP) mon->hp = mon->maxHP; return FALSE; }
    if ((item == ITEM_ANTIDOTE || item == ITEM_HEAL_POWDER) && mon->status == 1)
    { mon->status = 0; return FALSE; }
    return TRUE;
}
static void Reset(void)
{
    memset(&save1, 0, sizeof(save1)); memset(&save2, 0, sizeof(save2));
    memset(gPlayerParty, 0, sizeof(gPlayerParty));
    memset(&gMain, 0, sizeof(gMain)); memset(&gPartyMenu, 0, sizeof(gPartyMenu));
    memset(&gPaletteFade, 0, sizeof(gPaletteFade));
    gBattleTypeFlags = gWirelessCommType = gReceivedRemoteLinkPlayers = 0;
    secretFlags = secretItem = 0;
    busy = linked = coop = script = failRemoval = removals = 0;
    pyramid = PYRAMID_LOCATION_NONE;
    gPartyMenu.menuType = PARTY_MENU_TYPE_FIELD;
    gPartyMenu.action = PARTY_ACTION_CHOOSE_MON;
    gPartyMenu.exitCallback = CB2_ReturnToFieldWithOpenMenu;
    gPlayerPartyCount = PARTY_SIZE;
    for (unsigned i = 0; i < PARTY_SIZE; i++)
    { gPlayerParty[i].box.hasSpecies = TRUE; gPlayerParty[i].hp = 90; gPlayerParty[i].maxHP = 100; }
    gActiveBattler = 3; gPotentialItemEffectBattler = 2;
}
static void Own(unsigned slot, u16 item, u16 count)
{ save1.bagPocket_Items[slot].itemId = item; save1.bagPocket_Items[slot].quantity = count; }
int main(void)
{
    struct AutoHealPlan plan;
    struct Pokemon before[PARTY_SIZE];
    Reset(); memcpy(before, gPlayerParty, sizeof(before));
    assert(WorldAutoHeal_Run() == AUTO_HEAL_NOTHING);
    assert(!memcmp(before, gPlayerParty, sizeof(before)) && !removals);
    Reset(); Own(0, ITEM_POTION, 6); Own(1, ITEM_ORAN_BERRY, 2);
    assert(WorldAutoHeal_Run() == AUTO_HEAL_USED);
    assert(gPlayerParty[0].hp == 100 && gPlayerParty[5].hp == 100);
    assert(CountTotalItemQuantityInBag(ITEM_ORAN_BERRY) == 0);
    assert(CountTotalItemQuantityInBag(ITEM_POTION) == 2);
    assert(gActiveBattler == 3 && gPotentialItemEffectBattler == 2);
    Reset(); Own(0, ITEM_POTION, 6); Own(1, ITEM_REVIVE, 6);
    gPlayerParty[0].hp = 0; gPlayerParty[1].box.isEgg = TRUE;
    assert(WorldAutoHeal_Run() == AUTO_HEAL_USED);
    assert(gPlayerParty[0].hp == 0 && gPlayerParty[1].hp == 90);
    assert(CountTotalItemQuantityInBag(ITEM_REVIVE) == 6);
    Reset(); Own(0, ITEM_BURN_HEAL, 1); Own(1, ITEM_ANTIDOTE, 1);
    gPlayerParty[0].hp = 100; gPlayerParty[0].status = 1;
    assert(WorldAutoHeal_Run() == AUTO_HEAL_USED);
    assert(!gPlayerParty[0].status && gPlayerParty[0].box.markings == 1);
    assert(CountTotalItemQuantityInBag(ITEM_BURN_HEAL) == 1);
    Reset(); gPlayerPartyCount = 1; Own(0, ITEM_POTION, 1); Own(1, ITEM_FRESH_WATER, 1);
    memcpy(before, gPlayerParty, sizeof(before));
    assert(WorldAutoHeal_Run() == AUTO_HEAL_USED);
    assert(!CountTotalItemQuantityInBag(ITEM_POTION) && CountTotalItemQuantityInBag(ITEM_FRESH_WATER) == 1);
    assert(!memcmp(&before[1], &gPlayerParty[1], sizeof(before) - sizeof(before[0])));
    Reset(); Own(0, ITEM_HEAL_POWDER, 1); Own(1, ITEM_ANTIDOTE, 1);
    gPlayerParty[0].status = 1;
    assert(WorldAutoHeal_Run() == AUTO_HEAL_USED);
    assert(!gPlayerParty[0].status && gPlayerParty[0].hp == 90);
    assert(!CountTotalItemQuantityInBag(ITEM_HEAL_POWDER) && CountTotalItemQuantityInBag(ITEM_ANTIDOTE) == 1);
    Reset(); Own(0, ITEM_POTION, 1);
    for (unsigned i = 0; i < PARTY_SIZE; i++) gPlayerParty[i].hp = 100;
    memcpy(before, gPlayerParty, sizeof(before));
    assert(WorldAutoHeal_Run() == AUTO_HEAL_NOTHING);
    assert(!memcmp(before, gPlayerParty, sizeof(before)) && !removals);
    Reset(); Own(0, ITEM_POTION, 6); BuildPlan(&plan);
    gPlayerParty[5].box.personality++;
    assert(!CommitPlan(&plan) && !removals);
    Reset(); Own(0, ITEM_POTION, 6); BuildPlan(&plan);
    save1.bagPocket_Items[0].quantity--;
    assert(!CommitPlan(&plan) && !removals);
    Reset(); Own(0, ITEM_POTION, 6); BuildPlan(&plan); save2.encryptionKey++;
    assert(!CommitPlan(&plan) && !removals);
    Reset(); Own(0, ITEM_POTION, 6); BuildPlan(&plan); busy = 1;
    assert(!CommitPlan(&plan) && !removals);
    Reset(); Own(0, ITEM_POTION, 1); Own(1, ITEM_ORAN_BERRY, 1);
    memcpy(before, gPlayerParty, sizeof(before)); failRemoval = 2;
    assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    assert(!memcmp(before, gPlayerParty, sizeof(before)));
    assert(CountTotalItemQuantityInBag(ITEM_POTION) == 1 && CountTotalItemQuantityInBag(ITEM_ORAN_BERRY) == 1);
    Reset(); busy = 1; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); linked = 1; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); coop = 1; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); script = 1; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); gMain.inBattle = TRUE; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); gPartyMenu.menuType = PARTY_MENU_TYPE_UNION_ROOM_TRADE;
    assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); gPartyMenu.exitCallback = NULL; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); gPaletteFade.active = TRUE; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    Reset(); gReceivedRemoteLinkPlayers = TRUE; assert(WorldAutoHeal_Run() == AUTO_HEAL_REFUSED);
    puts("owned auto-heal transaction fixture passed (not native acceptance)");
    return 0;
}
