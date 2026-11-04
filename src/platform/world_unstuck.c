#if defined(PORTABLE) && !defined(_WIN32)
#include "global.h"
#include "heal_location.h"
#include "event_object_movement.h"
#include "fieldmap.h"
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
#include "platform/world_activity.h"
#include "constants/battle_frontier.h"
#include "constants/flags.h"
#include "constants/vars.h"
#include "constants/map_types.h"
#include "constants/heal_locations.h"
#include "constants/maps.h"
#include "constants/global.h"
#include "platform/world_unstuck.h"

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
bool8 WorldUnstuck_AllowedDeparture(void)
{
    if (!gSaveBlock1Ptr || !FlagGet(FLAG_SYS_POKEMON_GET)
        || gMain.callback1 != CB1_Overworld || gMain.callback2 != CB2_Overworld
        || gMain.inBattle || gPaletteFade.active || ScriptContext_IsEnabled()
        || gPlayerAvatar.tileTransitionState || (gPlayerAvatar.flags & PLAYER_AVATAR_FLAG_UNDERWATER)
        || gMapHeader.mapType == MAP_TYPE_UNDERWATER || gWirelessCommType
        || NativeLink_IsActive() || WorldActivity_OwnsFieldInput()
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
#endif
