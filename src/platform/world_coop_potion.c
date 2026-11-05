#ifdef PORTABLE
#include "global.h"
#include "constants/items.h"
#include "platform/world_coop_potion.h"

bool8 WorldCoop_IsPotion(u16 item)
{
    return item == ITEM_POTION || item == ITEM_SUPER_POTION
        || item == ITEM_HYPER_POTION || item == ITEM_MAX_POTION;
}

u16 WorldCoop_PotionHeal(u16 item, u16 hp, u16 maxHP)
{
    u16 amount, missing;
    if (!hp || !maxHP || maxHP > 999 || hp >= maxHP) return 0;
    switch (item)
    {
    case ITEM_POTION: amount = 20; break;
    case ITEM_SUPER_POTION: amount = 50; break;
    case ITEM_HYPER_POTION: amount = 200; break;
    case ITEM_MAX_POTION: amount = maxHP; break;
    default: return 0;
    }
    missing = maxHP - hp;
    return amount < missing ? amount : missing;
}
#endif
