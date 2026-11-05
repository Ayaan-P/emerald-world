#ifndef GUARD_PLATFORM_MEGA_GAME_H
#define GUARD_PLATFORM_MEGA_GAME_H
#ifdef PORTABLE
/* Locked until graphics, switching, abilities and private-save integration
 * have been verified together. Component tests may explicitly enable it. */
#ifndef MEGA_FEATURE_READY
#define MEGA_FEATURE_READY 0
#endif
#define MEGA_MOVE_CHOICE_BIT 0x80
void MegaGame_Reset(void);
bool8 MegaGame_CanSelect(u8 battler);
bool8 MegaGame_CanQueue(u8 battler);
bool8 MegaGame_ToggleSelection(u8 battler);
u8 MegaGame_ChoiceBit(u8 battler);
void MegaGame_ClearSelection(u8 battler);
bool8 MegaGame_Queue(u8 battler);
void MegaGame_CancelQueue(u8 battler);
bool8 MegaGame_Apply(u8 battler);
bool8 MegaGame_OnSwitchIn(u8 battler);
bool8 MegaGame_PublishForm(u8 battler, u8 kind);
bool8 MegaGame_ObserveForm(u8 battler, u8 form, u8 partyIndex);
u8 MegaGame_ActiveForm(u8 battler);
#endif
#endif
