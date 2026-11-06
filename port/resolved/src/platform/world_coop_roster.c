#ifdef PORTABLE
#include "global.h"
#include "platform/world_coop_roster.h"
#include <string.h>

bool8 CoopRoster_Init(struct CoopRoster *roster, u8 validMask, const u8 staged[COOP_ROSTER_STAGE_SLOTS])
{
    struct CoopRoster result = {0};
    u8 i, seen = 0;
    if (!roster || !staged || (validMask & ~0x3F)) return FALSE;
    for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
    {
        u8 original = staged[i];
        if (original != COOP_ROSTER_EMPTY)
        {
            if (original >= COOP_ROSTER_PRIVATE_SLOTS || !(validMask & (1u << original))
             || (seen & (1u << original))) return FALSE;
            seen |= 1u << original;
        }
        result.staged[i] = original;
    }
    result.validMask = validMask;
    *roster = result;
    return TRUE;
}

bool8 CoopRoster_Plan(const struct CoopRoster *roster, u8 incoming, u8 activeStage, struct CoopRosterPlan *plan)
{
    u8 i, chosen = COOP_ROSTER_EMPTY;
    struct CoopRosterPlan result;
    if (!roster || !plan || incoming >= COOP_ROSTER_PRIVATE_SLOTS
     || activeStage >= COOP_ROSTER_STAGE_SLOTS || !(roster->validMask & (1u << incoming))
     || roster->staged[activeStage] == incoming) return FALSE;
    for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
        if (roster->staged[i] == incoming) { chosen = i; break; }
    if (chosen == COOP_ROSTER_EMPTY)
    {
        /* Prefer an unused stage slot, then an inactive slot. */
        for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
            if (i != activeStage && roster->staged[i] == COOP_ROSTER_EMPTY) { chosen = i; break; }
        if (chosen == COOP_ROSTER_EMPTY)
            for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
                if (i != activeStage) { chosen = i; break; }
    }
    if (chosen == COOP_ROSTER_EMPTY) return FALSE;
    result.stage = chosen; result.outgoing = roster->staged[chosen];
    result.incoming = incoming; result.activeStage = activeStage;
    memcpy(result.expected, roster->staged, sizeof(result.expected));
    *plan = result;
    return TRUE;
}

bool8 CoopRoster_Commit(struct CoopRoster *roster, const struct CoopRosterPlan *plan, u8 currentActiveStage, const u8 participation[COOP_ROSTER_ENEMY_SLOTS], u8 knockedStageMask)
{
    struct CoopRoster result;
    u8 i;
    if (!roster || !plan || !participation || (knockedStageMask & ~7) || plan->stage >= COOP_ROSTER_STAGE_SLOTS
     || plan->activeStage >= COOP_ROSTER_STAGE_SLOTS || plan->activeStage != currentActiveStage
     || plan->stage == plan->activeStage
     || plan->incoming >= COOP_ROSTER_PRIVATE_SLOTS || !(roster->validMask & (1u << plan->incoming))
     || roster->staged[plan->stage] != plan->outgoing
     || memcmp(roster->staged, plan->expected, sizeof(plan->expected))) return FALSE;
    for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
        if (i != plan->stage && roster->staged[i] == plan->incoming) return FALSE;
    result = *roster;
    for (i = 0; i < COOP_ROSTER_ENEMY_SLOTS; i++)
        if (!CoopRoster_Record(&result, i, participation[i])) return FALSE;
    for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
    {
        u8 original = result.staged[i];
        if (original == COOP_ROSTER_EMPTY) continue;
        if (knockedStageMask & (1u << i)) result.knockedOff |= 1u << original;
        else result.knockedOff &= ~(1u << original);
    }
    result.staged[plan->stage] = plan->incoming;
    *roster = result;
    return TRUE;
}

bool8 CoopRoster_Record(struct CoopRoster *roster, u8 enemySlot, u8 stageMask)
{
    u8 i, mask = 0;
    if (!roster || enemySlot >= COOP_ROSTER_ENEMY_SLOTS || (stageMask & ~0x7)) return FALSE;
    for (i = 0; i < COOP_ROSTER_STAGE_SLOTS; i++)
        if ((stageMask & (1u << i)) && roster->staged[i] != COOP_ROSTER_EMPTY)
            mask |= 1u << roster->staged[i];
    roster->participated[enemySlot] |= mask;
    return TRUE;
}

u8 CoopRoster_RewardMask(const struct CoopRoster *roster, u8 enemySlot, u8 currentStageMask)
{
    struct CoopRoster copy;
    if (!roster) return 0;
    copy = *roster;
    return CoopRoster_Record(&copy, enemySlot, currentStageMask) ? copy.participated[enemySlot] : 0;
}
#endif
