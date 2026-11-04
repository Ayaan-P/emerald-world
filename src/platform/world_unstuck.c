#if defined(PORTABLE) && !defined(_WIN32)
#include "global.h"
#include <time.h>
#include <string.h>
#include "heal_location.h"
#include "event_object_movement.h"
#include "fieldmap.h"
#include "field_effect.h"
#include "field_player_avatar.h"
#include "event_object_lock.h"
#include "task.h"
#include "metatile_behavior.h"
#include "battle_pike.h"
#include "battle_pyramid.h"
#include "event_data.h"
#include "field_specials.h"
#include "link.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "safari_zone.h"
#include "script.h"
#include "platform/native_link.h"
#include "platform/native_unstuck.h"
#include "platform/world_bridge.h"
#include "platform/link_transport.h"
#include "platform/world_activity.h"
#include "platform/world_catalog.h"
#include "constants/battle_frontier.h"
#include "constants/flags.h"
#include "constants/vars.h"
#include "constants/map_types.h"
#include "constants/metatile_behaviors.h"
#include "constants/heal_locations.h"
#include "constants/maps.h"
#include "constants/global.h"
#include "platform/world_unstuck.h"
#include "platform/unstuck_landing.h"

static const unsigned sAllowedHealLocations[] = {
        HEAL_LOCATION_LITTLEROOT_TOWN_BRENDANS_HOUSE_2F,
        HEAL_LOCATION_LITTLEROOT_TOWN_MAYS_HOUSE_2F,
        HEAL_LOCATION_PETALBURG_CITY, HEAL_LOCATION_SLATEPORT_CITY,
        HEAL_LOCATION_MAUVILLE_CITY, HEAL_LOCATION_RUSTBORO_CITY,
        HEAL_LOCATION_FORTREE_CITY, HEAL_LOCATION_LILYCOVE_CITY,
        HEAL_LOCATION_MOSSDEEP_CITY, HEAL_LOCATION_SOOTOPOLIS_CITY,
        HEAL_LOCATION_EVER_GRANDE_CITY, HEAL_LOCATION_OLDALE_TOWN,
        HEAL_LOCATION_DEWFORD_TOWN, HEAL_LOCATION_LAVARIDGE_TOWN,
        HEAL_LOCATION_FALLARBOR_TOWN, HEAL_LOCATION_VERDANTURF_TOWN,
        HEAL_LOCATION_PACIFIDLOG_TOWN, HEAL_LOCATION_EVER_GRANDE_CITY_POKEMON_LEAGUE,
        HEAL_LOCATION_BATTLE_FRONTIER_OUTSIDE_EAST,
    };
static bool8 IsAllowedHealId(unsigned id)
{
    unsigned i;
    for (i = 0; i < ARRAY_COUNT(sAllowedHealLocations); i++)
        if (sAllowedHealLocations[i] == id) return TRUE;
    return FALSE;
}

unsigned WorldUnstuck_HealDestination(const struct WarpData *warp, u8 playerGender)
{
    /* Only locations actually assigned by the game's respawn scripts. The
     * wider Fly/whiteout table also contains locations that are not visited
     * Centers or the player's own initial home. Compare exact coordinates,
     * since several heal locations share the same map. */
    unsigned i;
    if (playerGender != MALE && playerGender != FEMALE) return 0;
    if (!warp || warp->warpId != WARP_ID_NONE || warp->mapGroup < 0 || warp->mapNum < 0 || warp->x < 0 || warp->y < 0)
        return 0;
    for (i = 0; i < ARRAY_COUNT(sAllowedHealLocations); i++) {
        const struct HealLocation *location = GetHealLocation(sAllowedHealLocations[i]);
        if ((sAllowedHealLocations[i] == HEAL_LOCATION_LITTLEROOT_TOWN_BRENDANS_HOUSE_2F && playerGender != MALE)
            || (sAllowedHealLocations[i] == HEAL_LOCATION_LITTLEROOT_TOWN_MAYS_HOUSE_2F && playerGender != FEMALE)) continue;
        if (location && location->mapGroup == warp->mapGroup && location->mapNum == warp->mapNum
            && location->x == warp->x && location->y == warp->y) return sAllowedHealLocations[i];
    }
    return 0;
}

bool8 WorldUnstuck_ConservativelyBoxed(void)
{
    unsigned direction;
    struct ObjectEvent *player;
    if (gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return FALSE;
    player = &gObjectEvents[gPlayerAvatar.objectEventId];
    if (!player->active || !player->isPlayer) return FALSE;
    for (direction = DIR_SOUTH; direction <= DIR_EAST; direction++) {
        s16 x = player->currentCoords.x, y = player->currentCoords.y;
        u8 behavior;
        MoveCoords(direction, &x, &y);
        behavior = MapGridGetMetatileBehaviorAt(x, y);
        /* Never invoke CheckForObjectEventCollision: ledges and boulders in
         * that routine can mutate game state while merely checking. */
        if (GetCollisionAtCoords(player, x, y, direction) != COLLISION_IMPASSABLE
            || GetLedgeJumpDirection(x, y, direction) != DIR_NONE
            || MetatileBehavior_IsSurfableFishableWater(behavior)
            || MetatileBehavior_IsWarpDoor(behavior)
            || MetatileBehavior_IsNonAnimDoor(behavior)) return FALSE;
    }
    return TRUE;
}
static bool8 Unstuck_EventHazard(const struct MapEvents *events, int x, int y)
{
    unsigned i;
    for (i=0; i<events->warpCount; i++)
        if (events->warps[i].x==x && events->warps[i].y==y) return TRUE;
    for (i=0; i<events->coordEventCount; i++)
        if (events->coordEvents[i].x==x && events->coordEvents[i].y==y) return TRUE;
    for (i=0; i<events->objectEventCount; i++) {
        const struct ObjectEventTemplate *object=&events->objectEvents[i];
        if (object->flagId && FlagGet(object->flagId)) continue;
        if (abs(x-object->x) <= object->movementRangeX && abs(y-object->y) <= object->movementRangeY) return TRUE;
    }
    return FALSE;
}

bool8 WorldUnstuck_BuildStaticGrid(unsigned group, unsigned num, const struct MapHeader *map,
                                   u8 *plain, unsigned capacity)
{
    const struct WorldCatalogMap *catalog=WorldCatalog_Find(group,num);
    const struct MapLayout *layout;
    const struct MapEvents *events;
    unsigned x,y,width,height;
    if (!plain || !catalog || !map || map != Overworld_GetMapHeaderByGroupAndId(group,num)) return FALSE;
    layout=map->mapLayout; events=map->events;
    if (!layout || !events || !layout->map || !layout->primaryTileset || !layout->secondaryTileset
        || !layout->primaryTileset->metatileAttributes || !layout->secondaryTileset->metatileAttributes
        || (events->warpCount && !events->warps) || (events->coordEventCount && !events->coordEvents)
        || (events->objectEventCount && !events->objectEvents)
        || layout->width <= 0 || layout->height <= 0 || layout->width > 128 || layout->height > 128
        || layout->width * layout->height > 8192) return FALSE;
    width=layout->width; height=layout->height;
    if (width != catalog->width || height != catalog->height || capacity < width*height
        || !WorldCatalog_Coords(group,num,width-1,height-1)) return FALSE;
    for (y=0; y<height; y++) for (x=0; x<width; x++) {
        unsigned cell=x+y*width, id;
        u16 block=layout->map[cell];
        const u16 *attributes;
        plain[cell]=FALSE;
        if (block==MAPGRID_UNDEFINED || UNPACK_COLLISION(block)
            || UNPACK_ELEVATION(block)!=ELEVATION_DEFAULT) continue;
        id=UNPACK_METATILE(block);
        if (!WorldCatalog_Metatile(group,num,id)) continue;
        attributes=id<NUM_METATILES_IN_PRIMARY ? layout->primaryTileset->metatileAttributes : layout->secondaryTileset->metatileAttributes;
        if (UNPACK_BEHAVIOR(attributes[id<NUM_METATILES_IN_PRIMARY ? id : id-NUM_METATILES_IN_PRIMARY]) != MB_NORMAL
            || Unstuck_EventHazard(events,x,y)) continue;
        plain[cell]=TRUE;
    }
    return TRUE;
}

bool8 WorldUnstuck_BuildLoadedGrid(u8 *plain, u8 *clear, unsigned capacity)
{
    const struct MapLayout *layout=gMapHeader.mapLayout;
    const struct MapEvents *events=gMapHeader.events;
    unsigned x, y, i, width, height;
    if (!plain || !clear || plain==clear || !gSaveBlock1Ptr || gMain.callback2 != CB2_Overworld
        || !layout || !events || !gBackupMapLayout.map
        || (events->warpCount && !events->warps) || (events->coordEventCount && !events->coordEvents)
        || (events->objectEventCount && !events->objectEvents)
        || layout->width <= 0 || layout->height <= 0 || layout->width > 128 || layout->height > 128
        || layout->width * layout->height > 8192) return FALSE;
    width=layout->width; height=layout->height;
    if (capacity < width * height || gBackupMapLayout.width < (int)width + MAP_OFFSET_W
        || gBackupMapLayout.height < (int)height + MAP_OFFSET_H) return FALSE;
    for (y=0; y<height; y++) for (x=0; x<width; x++) {
        unsigned cell=x+y*width;
        int gx=x+MAP_OFFSET, gy=y+MAP_OFFSET;
        plain[cell] = !MapGridGetCollisionAt(gx,gy)
            && MapGridGetElevationAt(gx,gy)==ELEVATION_DEFAULT
            && MapGridGetMetatileBehaviorAt(gx,gy)==MB_NORMAL
            && !Unstuck_EventHazard(events,x,y);
        clear[cell]=plain[cell];
        for (i=0; clear[cell] && i<OBJECT_EVENTS_COUNT; i++) {
            const struct ObjectEvent *object=&gObjectEvents[i];
            if (object->active && !object->isPlayer && object->currentCoords.x==gx && object->currentCoords.y==gy)
                clear[cell]=FALSE;
        }
    }
    return TRUE;
}

bool8 WorldUnstuck_AllowedDeparture(void)
{
    if (!gSaveBlock1Ptr || !FlagGet(FLAG_SYS_POKEMON_GET)
        || gMain.callback1 != CB1_Overworld || gMain.callback2 != CB2_Overworld
        || gMain.inBattle || gPaletteFade.active || ScriptContext_IsEnabled()
        || gPlayerAvatar.tileTransitionState || (gPlayerAvatar.flags & PLAYER_AVATAR_FLAG_UNDERWATER)
        || gMapHeader.mapType == MAP_TYPE_UNDERWATER || gWirelessCommType
        || NativeLink_IsActive() || WorldActivity_OwnsFieldInput()
        || LinkTransport_OfferPending() || LinkTransport_TagOfferPending()
        || LinkTransport_PendingInvitation() || LinkTransport_PendingTag()
        || GetSafariZoneFlag() || InBattlePike() || CurrentBattlePyramidLocation() != PYRAMID_LOCATION_NONE
        || InMultiPartnerRoom()) return FALSE;
    /* Restrict to places where a normal Fly/Teleport or Escape Rope departure
     * is supported. Special interiors and story-locked maps fail closed. */
    return Overworld_MapTypeAllowsTeleportAndFly(gMapHeader.mapType) || gMapHeader.allowEscaping;
}

bool8 WorldUnstuck_StoryAllowsDestination(unsigned healId)
{
    if (!IsAllowedHealId(healId)) return FALSE;
    if (healId == HEAL_LOCATION_SOOTOPOLIS_CITY) {
        u16 city = VarGet(VAR_SOOTOPOLIS_CITY_STATE), sky = VarGet(VAR_SKY_PILLAR_STATE);
        if ((city > 0 && city < 6) || (sky > 0 && sky < 3)) return FALSE;
    }
    if (healId == HEAL_LOCATION_EVER_GRANDE_CITY_POKEMON_LEAGUE
        && !FlagGet(FLAG_LANDMARK_POKEMON_LEAGUE)) return FALSE;
    if (healId == HEAL_LOCATION_BATTLE_FRONTIER_OUTSIDE_EAST
        && !FlagGet(FLAG_SYS_GAME_CLEAR)) return FALSE;
    return TRUE;
}
enum WorldUnstuckPlanResult WorldUnstuck_Plan(struct WorldUnstuckPlan *out)
{
    static u8 grid[8192];
    struct WorldUnstuckPlan plan = {0};
    const struct HealLocation *heal;
    const struct MapHeader *destination;
    const struct ObjectEvent *player;
    int x, y;
    if (!out || !gSaveBlock2Ptr || !WorldUnstuck_AllowedDeparture()
        || gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return UNSTUCK_PLAN_BLOCKED;
    player=&gObjectEvents[gPlayerAvatar.objectEventId];
    if (!player->active || !player->isPlayer) return UNSTUCK_PLAN_BLOCKED;
    x=player->currentCoords.x-MAP_OFFSET; y=player->currentCoords.y-MAP_OFFSET;
    if (x<0 || y<0 || x>127 || y>127 || gSaveBlock1Ptr->location.mapGroup<0 || gSaveBlock1Ptr->location.mapNum<0
        || !WorldCatalog_Coords(gSaveBlock1Ptr->location.mapGroup,gSaveBlock1Ptr->location.mapNum,x,y))
        return UNSTUCK_PLAN_BLOCKED;
    plan.healId=WorldUnstuck_HealDestination(&gSaveBlock1Ptr->lastHealLocation,gSaveBlock2Ptr->playerGender);
    if (!plan.healId || !WorldUnstuck_StoryAllowsDestination(plan.healId)) return UNSTUCK_PLAN_NO_HEAL;
    heal=GetHealLocation(plan.healId);
    if (!heal) return UNSTUCK_PLAN_NO_HEAL;
    destination=Overworld_GetMapHeaderByGroupAndId(heal->mapGroup,heal->mapNum);
    if (!WorldUnstuck_BuildStaticGrid(heal->mapGroup,heal->mapNum,destination,grid,sizeof(grid))
        || !Unstuck_SelectLanding(grid,grid,destination->mapLayout->width,destination->mapLayout->height,
                                  heal->x,heal->y,&plan.landingX,&plan.landingY)) return UNSTUCK_PLAN_NO_LANDING;
    plan.originGroup=gSaveBlock1Ptr->location.mapGroup; plan.originNum=gSaveBlock1Ptr->location.mapNum;
    plan.originX=x; plan.originY=y; plan.destinationGroup=heal->mapGroup; plan.destinationNum=heal->mapNum;
    plan.spawnX=heal->x; plan.spawnY=heal->y;
    *out=plan;
    return UNSTUCK_PLAN_OK;
}
bool8 WorldUnstuck_RevalidateArrival(const struct WorldUnstuckPlan *plan, bool8 occupancyComplete)
{
    static u8 plain[8192], clear[8192];
    const struct WorldCatalogMap *catalog;
    const struct ObjectEvent *player;
    const struct HealLocation *heal;
    if (!plan || !occupancyComplete || !gSaveBlock1Ptr || !gSaveBlock2Ptr
        || !WorldUnstuck_AllowedDeparture() || gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT)
        return FALSE;
    catalog=WorldCatalog_Find(plan->destinationGroup,plan->destinationNum);
    heal=GetHealLocation(plan->healId);
    if (!catalog || !heal || heal->mapGroup != (int)plan->destinationGroup
        || heal->mapNum != (int)plan->destinationNum || heal->x != plan->spawnX || heal->y != plan->spawnY)
        return FALSE;
    player=&gObjectEvents[gPlayerAvatar.objectEventId];
    if (!player->active || !player->isPlayer || gSaveBlock1Ptr->location.mapGroup != (int)plan->destinationGroup
        || gSaveBlock1Ptr->location.mapNum != (int)plan->destinationNum
        || player->currentCoords.x-MAP_OFFSET != plan->landingX
        || player->currentCoords.y-MAP_OFFSET != plan->landingY
        || WorldUnstuck_HealDestination(&gSaveBlock1Ptr->lastHealLocation,gSaveBlock2Ptr->playerGender) != plan->healId
        || !WorldUnstuck_StoryAllowsDestination(plan->healId)) return FALSE;
    if (!gMapHeader.mapLayout || gMapHeader.mapLayout->width != (int)catalog->width
        || gMapHeader.mapLayout->height != (int)catalog->height
        || !WorldUnstuck_BuildLoadedGrid(plain,clear,sizeof(plain))) return FALSE;
    return Unstuck_IsPlannedLandingStillSafe(plain,clear,catalog->width,catalog->height,
                                            plan->spawnX,plan->spawnY,plan->landingX,plan->landingY);
}
EWRAM_DATA static struct WorldUnstuckPlan sUnstuckPlan;
EWRAM_DATA static bool8 sUnstuckActive;

void WorldUnstuck_Reset(void)
{
    sUnstuckActive=FALSE;
    memset(&sUnstuckPlan,0,sizeof(sUnstuckPlan));
}

enum WorldUnstuckUseResult WorldUnstuck_Begin(void)
{
    struct WorldUnstuckPlan plan;
    enum NativeUnstuckResult reservation;
    time_t now;
    unsigned i;
    if (WorldBridge_Enabled()) return UNSTUCK_USE_ONLINE_UNSUPPORTED;
    if (sUnstuckActive || WorldUnstuck_Plan(&plan) != UNSTUCK_PLAN_OK) return UNSTUCK_USE_BLOCKED;
    /* CreateTask returns slot zero on exhaustion; verify capacity first. */
    for (i=0; i<NUM_TASKS; i++) if (!gTasks[i].isActive) break;
    if (i==NUM_TASKS) return UNSTUCK_USE_BLOCKED;
    now=time(NULL);
    if (now<=0) return UNSTUCK_USE_STORAGE_ERROR;
    reservation=NativeUnstuck_ReserveCurrent((uint64_t)now,WorldUnstuck_ConservativelyBoxed(),NULL);
    if (reservation==NATIVE_UNSTUCK_COOLDOWN) return UNSTUCK_USE_COOLDOWN;
    if (reservation!=NATIVE_UNSTUCK_ALLOWED) return UNSTUCK_USE_STORAGE_ERROR;
    sUnstuckPlan=plan; sUnstuckActive=TRUE;
    /* Match the engine's own Teleport setup for bikes, surfing and field flags. */
    Overworld_ResetStateAfterTeleport();
    SetPlayerAvatarTransitionFlags(PLAYER_AVATAR_FLAG_ON_FOOT);
    LockPlayerFieldControls(); FreezeObjectEvents();
    FldEff_TeleportWarpOut();
    return UNSTUCK_USE_STARTED;
}

bool8 WorldUnstuck_SetPlannedWarp(void)
{
    if (!sUnstuckActive) return FALSE;
    SetWarpDestination(sUnstuckPlan.destinationGroup,sUnstuckPlan.destinationNum,WARP_ID_NONE,
                       sUnstuckPlan.landingX,sUnstuckPlan.landingY);
    return TRUE;
}

bool8 WorldUnstuck_CompleteArrival(void)
{
    bool8 safe;
    if (!sUnstuckActive) return FALSE;
    /* This prototype is strictly offline. A connected game's remote occupancy
     * is never treated as complete by this path. */
    safe=!WorldBridge_Enabled() && WorldUnstuck_RevalidateArrival(&sUnstuckPlan,TRUE);
    sUnstuckActive=FALSE;
    if (safe) return FALSE;
    SetWarpDestination(sUnstuckPlan.originGroup,sUnstuckPlan.originNum,WARP_ID_NONE,
                       sUnstuckPlan.originX,sUnstuckPlan.originY);
    return TRUE;
}
#endif
