#ifndef GUARD_PLATFORM_WORLD_RALLY_H
#define GUARD_PLATFORM_WORLD_RALLY_H
#ifdef PORTABLE
#include "gba/types.h"

#define WORLD_RALLY_ROSTER 4
#define WORLD_RALLY_ROXANNE 1
/* Wire values are fixed. UI belongs to the caller, not this backend. */
enum WorldRallyPhase { WORLD_RALLY_NONE, WORLD_RALLY_GATHER, WORLD_RALLY_TRAVEL,
    WORLD_RALLY_ACTIVE, WORLD_RALLY_RETURN };
enum WorldRallyMemberState { WORLD_RALLY_INVITED = 1, WORLD_RALLY_READY,
    WORLD_RALLY_NOT_YET, WORLD_RALLY_MOVING, WORLD_RALLY_ARRIVED,
    WORLD_RALLY_RETURNING, WORLD_RALLY_STAYING, WORLD_RALLY_LEFT };
enum WorldRallyAction { WORLD_RALLY_REPORT, WORLD_RALLY_OFFER, WORLD_RALLY_ACCEPT,
    WORLD_RALLY_LATER, WORLD_RALLY_CANCEL, WORLD_RALLY_GO, WORLD_RALLY_LAND,
    WORLD_RALLY_FINISH, WORLD_RALLY_BACK, WORLD_RALLY_KEEP, WORLD_RALLY_HOME,
    WORLD_RALLY_FAIL };
struct WorldRallyMember { char name[25]; unsigned state, slot; };
struct WorldRallySnapshot {
    unsigned id, phase, scene, scope, count;
    char owner[25];
    struct WorldRallyMember members[WORLD_RALLY_ROSTER];
};
/* Main/game thread only. ASK is the startup default. AUTO still checks local
 * eligibility and cannot accept a busy player or move through a script/menu.
 * scope: 0 nearby (same map, <=12 tiles), 1 world. scene: ROXANNE only.
 * Request at Roxanne's approach after defeating the three Gym trainers locally.
 * Buttons must close their window and release THEIR lock before returning.
 * Commands return queue acceptance, never invented server approval/readiness. */
void WorldRally_SetAutoJoin(bool8 enabled);
bool8 WorldRally_GetAutoJoin(void);
bool8 WorldRally_Request(unsigned scene, unsigned scope);
bool8 WorldRally_Choose(unsigned action);
bool8 WorldRally_GetSnapshot(struct WorldRallySnapshot *out);
const char *WorldRally_Status(void);
bool8 WorldRally_HasReturn(void);
/* Bridge/engine hooks, not UI. No arbitrary warp or script execution API. */
void WorldRally_Init(const char *configPath);
void WorldRally_Update(void);
void WorldRally_Disconnected(void);
#endif
#endif
