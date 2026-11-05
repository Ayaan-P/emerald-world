#ifndef GUARD_PLATFORM_WORLD_COOP_POTION_H
#define GUARD_PLATFORM_WORLD_COOP_POTION_H
#ifdef PORTABLE
/* Gen 3 battle values; zero means unavailable or no effect. */
bool8 WorldCoop_IsPotion(u16 item);
u16 WorldCoop_PotionHeal(u16 item, u16 hp, u16 maxHP);
#endif
#endif
