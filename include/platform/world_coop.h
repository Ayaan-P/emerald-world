#ifndef GUARD_PLATFORM_WORLD_COOP_H
#define GUARD_PLATFORM_WORLD_COOP_H
#ifdef PORTABLE
#include "global.h"

/* The first three healthy, non-egg private party members fight. All six
 * private slots survive. Only balls may be used in the shared wild bag.
 * Encounters retain the generated wild mon or the complete NPC trainer team. */
void WorldCoop_CaptureWild(void);
bool8 WorldCoop_CaptureTrainer(void);
bool8 WorldCoop_IsTrainer(void);
bool8 WorldCoop_IsDoubleTrainer(void);
bool8 WorldCoop_HasSecondOpponent(void);
u16 WorldCoop_TrainerId(void);
void WorldCoop_CreateTrainerParty(void);
int WorldCoop_StartBattle(bool8 encounterOwner);
int WorldCoop_IsBattle(void);
struct Pokemon;
const struct Pokemon *WorldCoop_GetOwnMon(u8 originalSlot);
u8 WorldCoop_GetOwnPartyCount(void);
void WorldCoop_SetPartyMenuOrder(bool8 inMenuOrder);
u8 WorldCoop_Environment(void);
u8 WorldCoop_FieldWeather(void);
void WorldCoop_InitControllers(void);
/* A display-only projection, not a slave combat engine. The dispatcher calls
 * these observers only after authenticating and validating controller data.
 * Never pass multi-mon reserve responses to ObserveMonData. */
struct BattlePokemon;
struct WorldCoopPublicMon
{
    u16 species, hp, maxHP;
    u32 status;
    u8 level;
};
void WorldCoop_ObserveMonData(u8 battler, u8 partySlot, const struct BattlePokemon *mon);
void WorldCoop_ObserveController(u8 battler, const u8 *data);
bool8 WorldCoop_GetPublicMon(u8 battler, struct WorldCoopPublicMon *mon);
#define WORLD_COOP_MEDICINE_TAG 253
#define WORLD_COOP_MEDICINE_REPLY 0x8000
bool8 WorldCoop_CanSelectBattleItem(u16 item);
bool8 WorldCoop_CanUseMedicine(u16 item);
bool8 WorldCoop_ItemReplyValid(u16 reply);
u16 WorldCoop_SelectBattleItem(u16 item);
bool8 WorldCoop_MedicinePacketValid(const u8 *data, u16 size);
bool8 WorldCoop_ConsumeMedicine(const u8 *data);
bool8 WorldCoop_MedicineActionActive(u8 battler);
int WorldCoop_BeginMedicineAction(u8 battler, u16 reply);
int WorldCoop_AdvanceMedicineAction(u8 battler);
bool8 WorldCoop_CanSelectBall(u16 item);
bool8 WorldCoop_BallReplyValid(u16 reply);
u16 WorldCoop_SelectBall(u16 item);
void WorldCoop_EmitBallUse(u16 reply);
bool8 WorldCoop_EmitCatch(void);
bool8 WorldCoop_CatchPacketValid(const u8 *data, u16 size);
void WorldCoop_RecordCatchEvent(const u8 *data);
bool8 WorldCoop_BeginCatchRewards(void);
void WorldCoop_EmitDefeat(void);
void WorldCoop_AddPayday(u8 battler, u16 amount);
void WorldCoop_DoublePrize(u8 battler);
bool8 WorldCoop_RewardPacketValid(const u8 *data, u16 size);
void WorldCoop_RecordDefeat(const u8 *data);
/* Returns 0 for controller traffic, 1 for a consumed completion, -1 invalid. */
int WorldCoop_ReceiveCompletion(const u8 *data, u16 size, u8 sender);
bool8 WorldCoop_ReadyForPrivateRewards(void);
bool8 WorldCoop_CompletionCommitted(void);
bool8 WorldCoop_PreparePrivateRewards(void);
/* Local EXP, catch and evolution prompts run after intentional link closure. */
bool8 WorldCoop_IsPrivateRewards(void);
bool8 WorldCoop_NextReward(void);
void WorldCoop_Abort(void);
/* battle_main owns its static native engine/evolution callbacks. */
void WorldCoop_BeginPrivateRewards(void);
#endif
#endif
