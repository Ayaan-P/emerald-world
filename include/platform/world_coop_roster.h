#ifndef GUARD_PLATFORM_WORLD_COOP_ROSTER_H
#define GUARD_PLATFORM_WORLD_COOP_ROSTER_H
#ifdef PORTABLE
/* Battle-local original party identities. Never serialize this mapping. */
#define COOP_ROSTER_PRIVATE_SLOTS 6
#define COOP_ROSTER_STAGE_SLOTS 3
#define COOP_ROSTER_ENEMY_SLOTS 6
#define COOP_ROSTER_EMPTY 0xFF
struct CoopRoster
{
    u8 validMask;
    u8 staged[COOP_ROSTER_STAGE_SLOTS];
    u8 participated[COOP_ROSTER_ENEMY_SLOTS];
    u8 knockedOff;
};
struct CoopRosterPlan { u8 stage, outgoing, incoming, activeStage; u8 expected[COOP_ROSTER_STAGE_SLOTS]; };
bool8 CoopRoster_Init(struct CoopRoster *roster, u8 validMask, const u8 staged[COOP_ROSTER_STAGE_SLOTS]);
bool8 CoopRoster_Plan(const struct CoopRoster *roster, u8 incoming, u8 activeStage, struct CoopRosterPlan *plan);
bool8 CoopRoster_Commit(struct CoopRoster *roster, const struct CoopRosterPlan *plan, u8 currentActiveStage, const u8 participation[COOP_ROSTER_ENEMY_SLOTS], u8 knockedStageMask);
bool8 CoopRoster_Record(struct CoopRoster *roster, u8 enemySlot, u8 stageMask);
u8 CoopRoster_RewardMask(const struct CoopRoster *roster, u8 enemySlot, u8 currentStageMask);
#endif
#endif
