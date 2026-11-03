#ifndef GUARD_PLATFORM_WORLD_COOP_H
#define GUARD_PLATFORM_WORLD_COOP_H
#ifdef PORTABLE
#include "global.h"

/* First slice: first three healthy, non-egg party members fight. All six
 * private slots survive. Bag use/catching is unavailable in shared combat.
 * Capture only a standard, genuinely generated single wild encounter. */
void WorldCoop_CaptureWild(void);
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
bool8 WorldCoop_NextReward(void);
void WorldCoop_Abort(void);
/* battle_main owns its static native engine/evolution callbacks. */
void WorldCoop_BeginPrivateRewards(void);
#endif
#endif
