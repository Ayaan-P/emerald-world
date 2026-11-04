#ifdef PORTABLE
#include "global.h"
#include "battle.h"
#include "battle_pike.h"
#include "battle_pyramid.h"
#include "event_data.h"
#include "item.h"
#include "link.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "party_menu.h"
#include "pokemon.h"
#include "script.h"
#include "field_specials.h"
#include "platform/native_link.h"
#include "platform/world_activity.h"
#include "platform/world_coop.h"
#include "platform/party_autoheal.h"
#include "constants/battle_pyramid.h"
#include "constants/flags.h"
#include "constants/party_menu.h"
#include "constants/vars.h"
#include <string.h>

/* Fixed stock HP/status consumables only. Excludes revives, Sacred Ash, PP/EV
 * items, reusable flutes and the save-defined Enigma Berry effect. Berries are
 * owned medicine too. Prices are stock purchase prices, not HP-per-money or a
 * globally optimal shopping plan. Equal prices break by numeric item ID. */
static const u16 sMedicines[] =
{
    ITEM_POTION, ITEM_ANTIDOTE, ITEM_BURN_HEAL, ITEM_ICE_HEAL,
    ITEM_AWAKENING, ITEM_PARALYZE_HEAL, ITEM_FULL_RESTORE, ITEM_MAX_POTION,
    ITEM_HYPER_POTION, ITEM_SUPER_POTION, ITEM_FULL_HEAL,
    ITEM_FRESH_WATER, ITEM_SODA_POP, ITEM_LEMONADE, ITEM_MOOMOO_MILK,
    ITEM_ENERGY_POWDER, ITEM_ENERGY_ROOT, ITEM_HEAL_POWDER,
    ITEM_LAVA_COOKIE, ITEM_BERRY_JUICE,
    ITEM_CHERI_BERRY, ITEM_CHESTO_BERRY, ITEM_PECHA_BERRY, ITEM_RAWST_BERRY,
    ITEM_ASPEAR_BERRY, ITEM_ORAN_BERRY, ITEM_PERSIM_BERRY, ITEM_LUM_BERRY,
    ITEM_SITRUS_BERRY
};

struct AutoHealPlan
{
    struct Pokemon before[PARTY_SIZE], after[PARTY_SIZE];
    struct ItemSlot items[BAG_ITEMS_COUNT], berries[BAG_BERRIES_COUNT];
    u16 owned[ARRAY_COUNT(sMedicines)], used[ARRAY_COUNT(sMedicines)];
    u32 encryptionKey;
    u8 count, changed;
};

bool8 WorldAutoHeal_Available(void)
{
    /* The ordinary Party menu itself pauses the field and locks its controls.
     * Requiring unlocked controls or CB2_Overworld here would disable the real
     * action. Its field-only return callback distinguishes it from scripted
     * selections, trade and battle menus. The UI also checks its live callback.
     * A local tag alone is not busy: only activity/encounter ownership blocks. */
    return gSaveBlock1Ptr != NULL && gSaveBlock2Ptr != NULL
        && gPartyMenu.menuType == PARTY_MENU_TYPE_FIELD
        && gPartyMenu.action == PARTY_ACTION_CHOOSE_MON
        && gPartyMenu.exitCallback == CB2_ReturnToFieldWithOpenMenu
        && !gMain.inBattle && !gPaletteFade.active
        && !ScriptContext_IsEnabled()
        && !gWirelessCommType && !gReceivedRemoteLinkPlayers
        && !IsOverworldLinkActive()
        && !NativeLink_IsActive() && !WorldCoop_IsBattle()
        && !WorldCoop_IsPrivateRewards()
        && !WorldActivity_OwnsFieldInput() && !WorldActivity_IsEncounterPending()
        && !InUnionRoom() && !InMultiPartnerRoom() && !InBattlePike()
        && CurrentBattlePyramidLocation() == PYRAMID_LOCATION_NONE
        && !FlagGet(FLAG_STORING_ITEMS_IN_PYRAMID_BAG)
        && gPlayerPartyCount > 0 && gPlayerPartyCount <= PARTY_SIZE;
}

static bool8 TryMedicine(struct Pokemon *trial, u16 item, u8 slot)
{
    u16 hp = GetMonData(trial, MON_DATA_HP);
    u32 status = GetMonData(trial, MON_DATA_STATUS);
    u8 active = gActiveBattler, potential = gPotentialItemEffectBattler;
    bool8 noEffect;

    /* FALSE means applied. Even a TRUE/no-effect call can change friendship.
     * All probes operate on a fresh local copy, never the private live party.
     * These fixed effects out of battle only alter the copy and these globals. */
    noEffect = PokemonUseItemEffects(trial, item, slot, 0, FALSE);
    gActiveBattler = active;
    gPotentialItemEffectBattler = potential;
    return !noEffect && (GetMonData(trial, MON_DATA_HP) > hp
        || GetMonData(trial, MON_DATA_STATUS) != status);
}

static void BuildPlan(struct AutoHealPlan *plan)
{
    unsigned i, slot;
    memset(plan, 0, sizeof(*plan));
    plan->count = gPlayerPartyCount;
    plan->encryptionKey = gSaveBlock2Ptr->encryptionKey;
    memcpy(plan->before, gPlayerParty, sizeof(plan->before));
    memcpy(plan->after, plan->before, sizeof(plan->after));
    memcpy(plan->items, gSaveBlock1Ptr->bagPocket_Items, sizeof(plan->items));
    memcpy(plan->berries, gSaveBlock1Ptr->bagPocket_Berries, sizeof(plan->berries));
    for (i = 0; i < ARRAY_COUNT(sMedicines); i++)
        plan->owned[i] = CountTotalItemQuantityInBag(sMedicines[i]);

    /* Party-slot order, repeatedly taking the cheapest currently applicable
     * owned unit. Partial healing is useful even when stock cannot finish. */
    for (slot = 0; slot < plan->count; slot++)
    {
        struct Pokemon *mon = &plan->after[slot];
        if (!GetMonData(mon, MON_DATA_SPECIES) || GetMonData(mon, MON_DATA_IS_EGG)
            || !GetMonData(mon, MON_DATA_HP))
            continue;
        for (;;)
        {
            unsigned best = ARRAY_COUNT(sMedicines);
            struct Pokemon bestMon;
            for (i = 0; i < ARRAY_COUNT(sMedicines); i++)
            {
                struct Pokemon trial;
                if (plan->used[i] >= plan->owned[i])
                    continue;
                if (best != ARRAY_COUNT(sMedicines)
                    && (GetItemPrice(sMedicines[i]) > GetItemPrice(sMedicines[best])
                        || (GetItemPrice(sMedicines[i]) == GetItemPrice(sMedicines[best])
                            && sMedicines[i] > sMedicines[best])))
                    continue;
                trial = *mon;
                if (TryMedicine(&trial, sMedicines[i], slot))
                {
                    best = i;
                    bestMon = trial;
                }
            }
            if (best == ARRAY_COUNT(sMedicines))
                break;
            *mon = bestMon;
            plan->used[best]++;
            plan->changed |= 1 << slot;
        }
    }
}

static bool8 CommitPlan(const struct AutoHealPlan *plan)
{
    unsigned i;
    u16 secretFlags, secretItem;
    /* No callbacks, frames or network polling between validation and commit.
     * Validate full encrypted identities/state, reserves, quantities and the
     * bag encryption key. No detached plan may overwrite a newer private party. */
    if (!WorldAutoHeal_Available() || plan->count != gPlayerPartyCount
        || plan->encryptionKey != gSaveBlock2Ptr->encryptionKey
        || memcmp(plan->before, gPlayerParty, sizeof(plan->before))
        || memcmp(plan->items, gSaveBlock1Ptr->bagPocket_Items, sizeof(plan->items))
        || memcmp(plan->berries, gSaveBlock1Ptr->bagPocket_Berries, sizeof(plan->berries)))
        return FALSE;
    for (i = 0; i < ARRAY_COUNT(sMedicines); i++)
        if (CountTotalItemQuantityInBag(sMedicines[i]) != plan->owned[i]
            || plan->used[i] > plan->owned[i])
            return FALSE;

    /* Stock removal also records Secret Base item use. Restore its bookkeeping
     * along with encrypted pocket bytes if any removal unexpectedly refuses. */
    secretFlags = VarGet(VAR_SECRET_BASE_LOW_TV_FLAGS);
    secretItem = VarGet(VAR_SECRET_BASE_LAST_ITEM_USED);
    for (i = 0; i < ARRAY_COUNT(sMedicines); i++)
    {
        if (plan->used[i] && !RemoveBagItem(sMedicines[i], plan->used[i]))
        {
            memcpy(gSaveBlock1Ptr->bagPocket_Items, plan->items, sizeof(plan->items));
            memcpy(gSaveBlock1Ptr->bagPocket_Berries, plan->berries, sizeof(plan->berries));
            VarSet(VAR_SECRET_BASE_LOW_TV_FLAGS, secretFlags);
            VarSet(VAR_SECRET_BASE_LAST_ITEM_USED, secretItem);
            return FALSE;
        }
    }
    for (i = 0; i < plan->count; i++)
        if (plan->changed & (1 << i))
            gPlayerParty[i] = plan->after[i];
    return TRUE;
}

enum AutoHealResult WorldAutoHeal_Run(void)
{
    struct AutoHealPlan plan;
    if (!WorldAutoHeal_Available())
        return AUTO_HEAL_REFUSED;
    BuildPlan(&plan);
    if (!plan.changed)
        return AUTO_HEAL_NOTHING;
    return CommitPlan(&plan) ? AUTO_HEAL_USED : AUTO_HEAL_REFUSED;
}
#endif
