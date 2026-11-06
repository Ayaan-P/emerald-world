#ifndef GUARD_PLATFORM_MEGA_GAME_H
#define GUARD_PLATFORM_MEGA_GAME_H
#ifdef PORTABLE
/* Native pair and return-to-field proofs passed. Unsupported builds can
 * explicitly disable the capability without changing world defaults. */
#ifndef MEGA_FEATURE_READY
#define MEGA_FEATURE_READY 1
#endif
#define MEGA_MOVE_CHOICE_BIT 0x80
#define MEGA_MOVE_CAN_SELECT_BIT 0x01
void MegaGame_Reset(void);
void MegaGame_CheckAcquisition(void);
bool8 MegaGame_CanSelect(u8 battler);
bool8 MegaGame_ReplyAllowed(u8 battler, u8 announced);
bool8 MegaGame_CanQueue(u8 battler);
bool8 MegaGame_ValidateMoveChoice(u8 battler, u8 choice, u8 target);
bool8 MegaGame_ToggleSelection(u8 battler);
u8 MegaGame_ChoiceBit(u8 battler);
void MegaGame_ClearSelection(u8 battler);
bool8 MegaGame_Queue(u8 battler);
void MegaGame_CancelQueue(u8 battler);
void MegaGame_Restore(u8 battler);
void MegaGame_RecalculateStats(u8 battler);
void MegaGame_RefreshSprite(u8 battler);
bool8 MegaGame_Apply(u8 battler);
bool8 MegaGame_OnSwitchIn(u8 battler);
bool8 MegaGame_PublishForm(u8 battler, u8 kind);
bool8 MegaGame_ObserveForm(u8 battler, u8 form, u8 partyIndex);
u8 MegaGame_ActiveForm(u8 battler);
#endif
#endif
