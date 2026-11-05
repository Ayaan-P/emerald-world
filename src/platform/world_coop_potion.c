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
        || item == ITEM_ICE_HEAL || item == ITEM_AWAKENING || item == ITEM_PARALYZE_HEAL;
}

bool8 WorldCoop_MedicineEffect(u16 item, u16 hp, u16 maxHP, u32 status, u16 *heal, u32 *newStatus)
{
    u16 amount = 0;
    u32 mask = 0;
    if (!heal || !newStatus || !hp || !maxHP || maxHP > 999 || hp > maxHP) return FALSE;
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
    default:
        if (!WorldCoop_IsHpMedicine(item)) return FALSE;
    }
    if (!amount && !(status & mask)) return FALSE;
    *heal = amount;
    *newStatus = status & ~mask;
    return TRUE;
}

#endif
