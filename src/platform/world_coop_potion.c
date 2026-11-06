#ifdef PORTABLE
#include "global.h"
#include "constants/items.h"
#include "constants/battle.h"
#include "platform/world_coop_potion.h"

bool8 WorldCoop_IsHpMedicine(u16 item)
{
    return item == ITEM_POTION || item == ITEM_SUPER_POTION
        || item == ITEM_HYPER_POTION || item == ITEM_MAX_POTION
        || item == ITEM_FRESH_WATER || item == ITEM_SODA_POP || item == ITEM_LEMONADE || item == ITEM_MOOMOO_MILK;
}

u16 WorldCoop_HpMedicineHeal(u16 item, u16 hp, u16 maxHP)
{
    u16 amount, missing;
    if (!hp || !maxHP || maxHP > 999 || hp >= maxHP) return 0;
    switch (item)
    {
    case ITEM_POTION: amount = 20; break;
    case ITEM_SUPER_POTION: amount = 50; break;
    case ITEM_HYPER_POTION: amount = 200; break;
    case ITEM_MAX_POTION: amount = maxHP; break;
    case ITEM_FRESH_WATER: amount = 50; break;
    case ITEM_SODA_POP: amount = 60; break;
    case ITEM_LEMONADE: amount = 80; break;
    case ITEM_MOOMOO_MILK: amount = 100; break;
    default: return 0;
    }
    missing = maxHP - hp;
    return amount < missing ? amount : missing;
}

bool8 WorldCoop_IsMedicine(u16 item)
{
    return WorldCoop_IsHpMedicine(item) || item == ITEM_ANTIDOTE || item == ITEM_BURN_HEAL
        || item == ITEM_ICE_HEAL || item == ITEM_AWAKENING || item == ITEM_PARALYZE_HEAL
        || item == ITEM_FULL_HEAL || item == ITEM_FULL_RESTORE
        || item == ITEM_REVIVE || item == ITEM_MAX_REVIVE;
}

bool8 WorldCoop_MedicineEffect(u16 item, u16 hp, u16 maxHP, u32 status, bool8 confused, u16 *heal, u32 *newStatus, bool8 *clearConfusion)
{
    u16 amount = 0;
    u32 mask = 0;
    bool8 cureConfusion = FALSE;
    if (!heal || !newStatus || !clearConfusion || !maxHP || maxHP > 999 || hp > maxHP) return FALSE;
    if (!hp)
    {
        if (item != ITEM_REVIVE && item != ITEM_MAX_REVIVE) return FALSE;
        *heal = item == ITEM_MAX_REVIVE ? maxHP : (maxHP / 2 ? maxHP / 2 : 1);
        *newStatus = status;
        *clearConfusion = FALSE;
        return TRUE;
    }
    if (item == ITEM_REVIVE || item == ITEM_MAX_REVIVE) return FALSE;
    if (WorldCoop_IsHpMedicine(item)) amount = WorldCoop_HpMedicineHeal(item, hp, maxHP);
    switch (item)
    {
    case ITEM_ANTIDOTE:
        if (status & STATUS1_PSN_ANY) mask = STATUS1_PSN_ANY | STATUS1_TOXIC_COUNTER;
        break;
    case ITEM_BURN_HEAL: mask = STATUS1_BURN; break;
    case ITEM_ICE_HEAL: mask = STATUS1_FREEZE; break;
    case ITEM_AWAKENING: mask = STATUS1_SLEEP; break;
    case ITEM_PARALYZE_HEAL: mask = STATUS1_PARALYSIS; break;
    case ITEM_FULL_HEAL:
    case ITEM_FULL_RESTORE:
        if (status & STATUS1_ANY) mask = STATUS1_ANY | STATUS1_TOXIC_COUNTER;
        cureConfusion = confused;
        if (item == ITEM_FULL_RESTORE) amount = maxHP - hp;
        break;
    default:
        if (!WorldCoop_IsHpMedicine(item)) return FALSE;
    }
    if (!amount && !(status & mask) && !cureConfusion) return FALSE;
    *heal = amount;
    *newStatus = status & ~mask;
    *clearConfusion = cureConfusion;
    return TRUE;
}

#endif
