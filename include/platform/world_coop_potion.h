#ifndef GUARD_PLATFORM_WORLD_COOP_POTION_H
#define GUARD_PLATFORM_WORLD_COOP_POTION_H
#ifdef PORTABLE
/* Gen 3 battle values; zero means unavailable or no effect. */
bool8 WorldCoop_IsHpMedicine(u16 item);
bool8 WorldCoop_IsMedicine(u16 item);
bool8 WorldCoop_MedicineEffect(u16 item, u16 hp, u16 maxHP, u32 status, bool8 confused, u16 *heal, u32 *newStatus, bool8 *clearConfusion);
u16 WorldCoop_HpMedicineHeal(u16 item, u16 hp, u16 maxHP);
#endif
#endif
