#if defined(PORTABLE) && !defined(_WIN32)
#include "global.h"
#include "heal_location.h"
#include "event_object_movement.h"
#include "fieldmap.h"
#include "metatile_behavior.h"
#include "constants/heal_locations.h"
#include "constants/maps.h"
#include "constants/global.h"
#include "platform/world_unstuck.h"

unsigned WorldUnstuck_HealDestination(const struct WarpData *warp, u8 playerGender)
{
    /* Only locations actually assigned by the game's respawn scripts. The
     * wider Fly/whiteout table also contains locations that are not visited
     * Centers or the player's own initial home. Compare exact coordinates,
     * since several heal locations share the same map. */
    static const unsigned allowed[] = {
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
    unsigned i;
    if (playerGender != MALE && playerGender != FEMALE) return 0;
    if (!warp || warp->warpId != WARP_ID_NONE || warp->mapGroup < 0 || warp->mapNum < 0 || warp->x < 0 || warp->y < 0)
        return 0;
    for (i = 0; i < ARRAY_COUNT(allowed); i++) {
        const struct HealLocation *location = GetHealLocation(allowed[i]);
        if ((allowed[i] == HEAL_LOCATION_LITTLEROOT_TOWN_BRENDANS_HOUSE_2F && playerGender != MALE)
            || (allowed[i] == HEAL_LOCATION_LITTLEROOT_TOWN_MAYS_HOUSE_2F && playerGender != FEMALE)) continue;
        if (location && location->mapGroup == warp->mapGroup && location->mapNum == warp->mapNum
            && location->x == warp->x && location->y == warp->y) return allowed[i];
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
#endif
