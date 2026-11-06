#ifdef PORTABLE
#include "global.h"
#include "constants/map_groups.h"
#include "constants/maps.h"
#include "constants/flags.h"
#include <string.h>

#define TRAVEL_CELLS 8192
#include "constants/metatile_behaviors.h"
#include "event_data.h"
#include "fieldmap.h"
#include "platform/world_bridge.h"
#include "platform/world_catalog.h"
#include "platform/world_travel.h"
#include "platform/world_activity.h"
#include "platform/native_link.h"
#include "main.h"
#include "task.h"
#include "link.h"
#include "overworld.h"
#include "palette.h"
#include "pokemon.h"
#include "script.h"
#include "menu.h"
#include "window.h"
#include "field_player_avatar.h"
#include "event_object_movement.h"
#include "heal_location.h"
#include "constants/heal_locations.h"
#include "constants/characters.h"
#include "constants/map_types.h"
#include "constants/moves.h"
#include "field_screen_effect.h"

static bool8 BlockedByEvents(const struct MapEvents *events, int x, int y);
static bool8 SafeFloor(u16 block, u8 behavior);

static bool8 BuildLandingGrid(const struct MapHeader *map, unsigned group, unsigned num, u8 *grid)
{
    const struct MapLayout *layout = map->mapLayout;
    unsigned x, y;
    if (!layout || !layout->map || !layout->primaryTileset || !layout->secondaryTileset
        || layout->width <= 0 || layout->height <= 0 || layout->width > 128 || layout->height > 128
        || layout->width * layout->height > TRAVEL_CELLS) return FALSE;
    for (y = 0; y < (unsigned)layout->height; y++) for (x = 0; x < (unsigned)layout->width; x++)
    {
        unsigned id;
        const u16 *attributes;
        u16 block = layout->map[x + y * layout->width];
        id = UNPACK_METATILE(block);
        grid[x + y * layout->width] = 0;
        if (!WorldCatalog_Metatile(group, num, id)) continue;
        attributes = id < NUM_METATILES_IN_PRIMARY ? layout->primaryTileset->metatileAttributes
            : layout->secondaryTileset->metatileAttributes;
        if (!attributes) continue;
        if (!SafeFloor(block, UNPACK_BEHAVIOR(attributes[id < NUM_METATILES_IN_PRIMARY ? id : id - NUM_METATILES_IN_PRIMARY]))
            || BlockedByEvents(map->events, x, y)
            || !WorldBridge_TravelTileClear(group, num, x, y)) continue;
        /* Already-loaded field scripts and moving NPCs can disagree with their
         * static templates. If visiting our current map, also check live state. */
        if (gSaveBlock1Ptr && group == (unsigned)gSaveBlock1Ptr->location.mapGroup
            && num == (unsigned)gSaveBlock1Ptr->location.mapNum)
        {
            unsigned i;
            if (MapGridGetCollisionAt(x + MAP_OFFSET, y + MAP_OFFSET)
                || MapGridGetElevationAt(x + MAP_OFFSET, y + MAP_OFFSET) != ELEVATION_DEFAULT) continue;
            for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
                if (gObjectEvents[i].active && gObjectEvents[i].currentCoords.x == (int)x + MAP_OFFSET
                    && gObjectEvents[i].currentCoords.y == (int)y + MAP_OFFSET) break;
            if (i < OBJECT_EVENTS_COUNT) continue;
        }
        grid[x + y * layout->width] = 1;
    }
    return TRUE;
}

static bool8 BlockedByEvents(const struct MapEvents *events, int x, int y)
{
    unsigned i;
    if (!events) return TRUE;
    for (i = 0; i < events->warpCount; i++)
        if (events->warps[i].x == x && events->warps[i].y == y) return TRUE;
    for (i = 0; i < events->coordEventCount; i++)
        if (events->coordEvents[i].x == x && events->coordEvents[i].y == y) return TRUE;
    for (i = 0; i < events->objectEventCount; i++)
    {
        const struct ObjectEventTemplate *o = &events->objectEvents[i];
        if (o->flagId && FlagGet(o->flagId)) continue;
        if (abs(x - o->x) <= o->movementRangeX && abs(y - o->y) <= o->movementRangeY) return TRUE;
    }
    return FALSE;
}

static bool8 SafeFloor(u16 block, u8 behavior)
{
    return block != MAPGRID_UNDEFINED && !UNPACK_COLLISION(block)
        && UNPACK_ELEVATION(block) == ELEVATION_DEFAULT && behavior == MB_NORMAL;
}

/* Flood from an ordinary Fly landing, so a friend behind an unopened gate
 * cannot become a shortcut. The supplied grid excludes occupied/script tiles.
 * Neither this bounded search nor its caller modifies the native map. */
static bool8 FindLanding(const u8 *grid, unsigned width, unsigned height,
    int startX, int startY, int friendX, int friendY, s16 *outX, s16 *outY)
{
    static u8 seen[TRAVEL_CELLS];
    static u16 queue[TRAVEL_CELLS];
    unsigned head = 0, tail = 0;
    static const s8 dx[] = {0, 0, -1, 1}, dy[] = {1, -1, 0, 0};
    if (!grid || !width || !height || width > 128 || height > 128
        || width * height > TRAVEL_CELLS || startX < 0 || startY < 0
        || (unsigned)startX >= width || (unsigned)startY >= height
        || friendX < 0 || friendY < 0 || (unsigned)friendX >= width
        || (unsigned)friendY >= height || !grid[startX + startY * width]) return FALSE;
    memset(seen, 0, width * height);
    queue[tail++] = startX + startY * width;
    seen[queue[0]] = 1;
    while (head < tail)
    {
        unsigned cell = queue[head++], i;
        int x = cell % width, y = cell / width;
        if (abs(x - friendX) + abs(y - friendY) == 1)
        {
            *outX = x;
            *outY = y;
            return TRUE;
        }
        for (i = 0; i < ARRAY_COUNT(dx); i++)
        {
            int nx = x + dx[i], ny = y + dy[i];
            unsigned next;
            if (nx < 0 || ny < 0 || (unsigned)nx >= width || (unsigned)ny >= height) continue;
            next = nx + ny * width;
            if (!grid[next] || seen[next]) continue;
            seen[next] = 1;
            queue[tail++] = next;
        }
    }
    return FALSE;
}

/* Towns only follows the newer public Fly restriction. Use each visiting
 * trainer's own flags, never a host's badges or campaign state. */
static u16 VisitedFlag(unsigned group, unsigned num)
{
    static const struct { unsigned group, num; u16 flag; } towns[] = {
#define TOWN(name) { MAP_GROUP(MAP_##name), MAP_NUM(MAP_##name), FLAG_VISITED_##name }
        TOWN(LITTLEROOT_TOWN), TOWN(OLDALE_TOWN), TOWN(DEWFORD_TOWN),
        TOWN(LAVARIDGE_TOWN), TOWN(FALLARBOR_TOWN), TOWN(VERDANTURF_TOWN),
        TOWN(PACIFIDLOG_TOWN), TOWN(PETALBURG_CITY), TOWN(SLATEPORT_CITY),
        TOWN(MAUVILLE_CITY), TOWN(RUSTBORO_CITY), TOWN(FORTREE_CITY),
        TOWN(LILYCOVE_CITY), TOWN(MOSSDEEP_CITY), TOWN(SOOTOPOLIS_CITY),
        TOWN(EVER_GRANDE_CITY)
#undef TOWN
    };
    unsigned i;
    for (i = 0; i < ARRAY_COUNT(towns); i++)
        if (towns[i].group == group && towns[i].num == num) return towns[i].flag;
    return 0;
}

static bool8 TravelStoryReady(unsigned group, unsigned num)
{
    if (group == MAP_GROUP(MAP_SOOTOPOLIS_CITY) && num == MAP_NUM(MAP_SOOTOPOLIS_CITY))
    {
        u16 state = VarGet(VAR_SOOTOPOLIS_CITY_STATE);
        /* These arrival scenes distinguish the native Fly pad from Dive by
         * exact coordinates, replace the layout and reposition actors. A
         * nearby-friend landing must not enter them from an invented spot. */
        return (state == 0 || state >= 6) && VarGet(VAR_SKY_PILLAR_STATE) != 1;
    }
    return TRUE;
}

enum { TRAVEL_IDLE, TRAVEL_REQUEST, TRAVEL_FRIENDS, TRAVEL_CONFIRM, TRAVEL_MESSAGE };
static struct {
    unsigned state, count, delay, group, num;
    unsigned page;
    bool8 nextPage;
    u8 window;
    bool8 locked, flightActive;
    unsigned flightGroup, flightNum, flightHeal;
    char names[6][25], target[25];
    const char *status;
    s16 landingX, landingY;
} sTravel = { .window = WINDOW_NONE, .status = "idle" };

bool8 WorldTravel_CanAllocateFly(void)
{
    unsigned i, free = 0;
    /* Departure concurrently owns Task_UseFly, Task_FlyOut and the native
     * Pokemon portrait task. CreateTask returns zero on exhaustion, not
     * TASK_NONE, so its return value cannot protect task zero. */
    for (i = 0; i < NUM_TASKS; i++) if (!gTasks[i].isActive) free++;
    return free >= 3;
}

unsigned WorldTravel_ArrivalFallback(void)
{
    struct WorldBridgePeer peer;
    unsigned i;
    int x, y;
    bool8 valid = FALSE;
    if (!sTravel.flightActive) return 0;
    sTravel.flightActive = FALSE;
    x = gSaveBlock1Ptr->pos.x;
    y = gSaveBlock1Ptr->pos.y;
    for (i = 0; WorldBridge_GetTravelPeer(i, &peer); i++)
    {
        if (strcmp(peer.name, sTravel.target)) continue;
        valid = peer.ready && peer.group == sTravel.flightGroup && peer.num == sTravel.flightNum
            && peer.group == (unsigned)gSaveBlock1Ptr->location.mapGroup
            && peer.num == (unsigned)gSaveBlock1Ptr->location.mapNum
            && abs((int)peer.x - x) + abs((int)peer.y - y) == 1
            && WorldBridge_TravelTileClear(peer.group, peer.num, x, y);
        break;
    }
    if (valid)
    {
        u16 block = PACK_ELEVATION(MapGridGetElevationAt(x + MAP_OFFSET, y + MAP_OFFSET))
            | PACK_COLLISION(MapGridGetCollisionAt(x + MAP_OFFSET, y + MAP_OFFSET));
        valid = SafeFloor(block, MapGridGetMetatileBehaviorAt(x + MAP_OFFSET, y + MAP_OFFSET))
            && !BlockedByEvents(gMapHeader.events, x, y);
        for (i = 0; valid && i < OBJECT_EVENTS_COUNT; i++)
            if (gObjectEvents[i].active && !gObjectEvents[i].isPlayer
                && gObjectEvents[i].currentCoords.x == x + MAP_OFFSET
                && gObjectEvents[i].currentCoords.y == y + MAP_OFFSET) valid = FALSE;
    }
    if (valid) { sTravel.status = "Arrived beside friend."; return 0; }
    /* No reservations or save rewinds. If a friend moves, disconnects or a
     * loaded script changes the tile, finish at the already-qualified native
     * Fly point instead of releasing controls on a stale custom landing. */
    sTravel.status = "Friend moved. Landing at the Fly point.";
    return sTravel.flightHeal;
}

static bool8 TravelField(void)
{
    return gSaveBlock1Ptr && gMain.callback1 == CB1_Overworld && gMain.callback2 == CB2_Overworld
        && !gMain.inBattle && !gPaletteFade.active && !ScriptContext_IsEnabled()
        && !gPlayerAvatar.tileTransitionState && !gWirelessCommType
        && !NativeLink_IsActive() && !WorldActivity_OwnsFieldInput();
}

bool8 WorldTravel_RallyTileSafe(unsigned group, unsigned num, s16 x, s16 y, unsigned elevation, bool8 online)
{
    const struct MapHeader *map;
    const struct MapLayout *layout;
    const u16 *attributes;
    unsigned id, i;
    u16 block;
    if (group > 127 || num > 127 || x < 0 || y < 0 || x > 127 || y > 127
        || elevation != ELEVATION_DEFAULT || !WorldCatalog_Coords(group, num, x, y)) return FALSE;
    map = Overworld_GetMapHeaderByGroupAndId(group, num);
    if (!map || !map->mapLayout) return FALSE;
    layout = map->mapLayout;
    if (!layout->map || !layout->primaryTileset || !layout->secondaryTileset
        || x >= layout->width || y >= layout->height) return FALSE;
    block = layout->map[x + y * layout->width];
    id = UNPACK_METATILE(block);
    if (!WorldCatalog_Metatile(group, num, id)) return FALSE;
    attributes = id < NUM_METATILES_IN_PRIMARY ? layout->primaryTileset->metatileAttributes
        : layout->secondaryTileset->metatileAttributes;
    if (!attributes || !SafeFloor(block, UNPACK_BEHAVIOR(attributes[id < NUM_METATILES_IN_PRIMARY
            ? id : id - NUM_METATILES_IN_PRIMARY]))
        || BlockedByEvents(map->events, x, y)
        || (online && !WorldBridge_TravelTileClear(group, num, x, y))) return FALSE;
    if (gSaveBlock1Ptr && group == (unsigned)gSaveBlock1Ptr->location.mapGroup
        && num == (unsigned)gSaveBlock1Ptr->location.mapNum)
    {
        if (MapGridGetCollisionAt(x + MAP_OFFSET, y + MAP_OFFSET)
            || MapGridGetElevationAt(x + MAP_OFFSET, y + MAP_OFFSET) != elevation
            || MapGridGetMetatileBehaviorAt(x + MAP_OFFSET, y + MAP_OFFSET) != MB_NORMAL) return FALSE;
        for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
            if (gObjectEvents[i].active && !gObjectEvents[i].isPlayer
                && gObjectEvents[i].currentCoords.x == x + MAP_OFFSET
                && gObjectEvents[i].currentCoords.y == y + MAP_OFFSET) return FALSE;
    }
    return TRUE;
}

bool8 WorldTravel_RallyWarp(unsigned group, unsigned num, s16 x, s16 y, unsigned elevation, bool8 online)
{
    unsigned i;
    if (!TravelField() || ArePlayerFieldControlsLocked() || WorldTravel_OwnsFieldInput()
        || !WorldTravel_RallyTileSafe(group, num, x, y, elevation, online)) return FALSE;
    for (i = 0; i < NUM_TASKS; i++) if (!gTasks[i].isActive) break;
    if (i == NUM_TASKS) return FALSE;
    SetWarpDestination(group, num, WARP_ID_NONE, x, y);
    DoWarp();
    return TRUE;
}

static void TravelEncode(u8 *dest, const char *text)
{
    for (; *text; text++, dest++)
    {
        unsigned char c = *text;
        if (c >= 'A' && c <= 'Z') *dest = CHAR_A + c - 'A';
        else if (c >= 'a' && c <= 'z') *dest = CHAR_a + c - 'a';
        else if (c >= '0' && c <= '9') *dest = CHAR_0 + c - '0';
        else if (c == '\n') *dest = CHAR_NEWLINE;
        else if (c == '.') *dest = CHAR_PERIOD;
        else if (c == '-') *dest = CHAR_HYPHEN;
        else if (c == '?') *dest = CHAR_QUESTION_MARK;
        else *dest = CHAR_SPACE;
    }
    *dest = EOS;
}

static void TravelPrint(const char *text, unsigned y)
{
    u8 encoded[128];
    TravelEncode(encoded, text);
    AddTextPrinterParameterized(sTravel.window, FONT_SMALL, encoded, 8, y, TEXT_SKIP_DRAW, NULL);
}

static void TravelCloseWindow(void)
{
    if (sTravel.window != WINDOW_NONE)
    {
        ClearStdWindowAndFrame(sTravel.window, TRUE);
        RemoveWindow(sTravel.window);
        sTravel.window = WINDOW_NONE;
    }
}

void WorldTravel_Close(void)
{
    TravelCloseWindow();
    if (sTravel.locked && gMain.callback2 == CB2_Overworld)
    {
        UnlockPlayerFieldControls();
        UnfreezeObjectEvents();
    }
    sTravel.locked = FALSE;
    sTravel.flightActive = FALSE;
    sTravel.state = TRAVEL_IDLE;
    sTravel.page = 0;
}

static bool8 TravelWindow(void)
{
    struct WindowTemplate window = { 0, 1, 1, 28, 18, 15, 0x125 };
    TravelCloseWindow();
    sTravel.window = AddWindow(&window);
    if (sTravel.window == WINDOW_NONE) { WorldTravel_Close(); return FALSE; }
    SetStandardWindowBorderStyle(sTravel.window, FALSE);
    sTravel.delay = 1;
    return TRUE;
}

static void TravelFriends(void)
{
    struct WorldBridgePeer peer;
    unsigned i;
    if (!TravelWindow()) return;
    TravelPrint("Friends   Choose a trainer to Fly to", 0);
    sTravel.count = 0;
    /* Leave room for page controls without enlarging the field window.
     * Confirmation re-resolves the chosen identity against live presence. */
    if (sTravel.page && !WorldBridge_GetTravelPeer(sTravel.page * ARRAY_COUNT(sTravel.names), &peer))
        sTravel.page = 0;
    for (i = 0; i < ARRAY_COUNT(sTravel.names)
        && WorldBridge_GetTravelPeer(sTravel.page * ARRAY_COUNT(sTravel.names) + i, &peer); i++)
    {
        strcpy(sTravel.names[sTravel.count++], peer.name);
        TravelPrint(peer.name, 24 + i * 12);
    }
    sTravel.nextPage = WorldBridge_GetTravelPeer((sTravel.page + 1) * ARRAY_COUNT(sTravel.names), &peer);
    i = sTravel.count;
    if (sTravel.nextPage) TravelPrint("Next page", 24 + i++ * 12);
    if (sTravel.page) TravelPrint("Previous page", 24 + i++ * 12);
    TravelPrint("Cancel", 24 + i * 12);
    if (!sTravel.count) TravelPrint("No friends are connected.", 48);
    InitMenuNormal(sTravel.window, FONT_SMALL, 0, 24, 12, i + 1, 0);
    CopyWindowToVram(sTravel.window, COPYWIN_FULL);
    sTravel.state = TRAVEL_FRIENDS;
    sTravel.status = "Choose a friend.";
}

static void TravelMessage(const char *message)
{
    sTravel.status = message;
    if (!TravelWindow()) return;
    TravelPrint(message, 16);
    TravelPrint("Press A or B to go back.", 112);
    CopyWindowToVram(sTravel.window, COPYWIN_FULL);
    sTravel.state = TRAVEL_MESSAGE;
}

/* Validate again on confirmation, not when drawing the friend list. */
static const char *TravelDestination(struct WorldBridgePeer *peer, unsigned *mon, s16 *x, s16 *y)
{
    unsigned i, j, flag;
    const struct MapHeader *map;
    static u8 grid[TRAVEL_CELLS];
    if (!FlagGet(FLAG_BADGE06_GET)) return "You need the Feather Badge.";
    for (i = 0; i < gPlayerPartyCount && i < PARTY_SIZE; i++)
    {
        if (!GetMonData(&gPlayerParty[i], MON_DATA_SPECIES) || GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)) continue;
        for (j = 0; j < MAX_MON_MOVES; j++)
            if (GetMonData(&gPlayerParty[i], MON_DATA_MOVE1 + j) == MOVE_FLY) break;
        if (j < MAX_MON_MOVES) break;
    }
    if (i == gPlayerPartyCount || i == PARTY_SIZE) return "A Pokemon must know Fly.";
    *mon = i;
    if (!Overworld_MapTypeAllowsTeleportAndFly(gMapHeader.mapType)) return "You cannot Fly from here.";
    for (i = 0; WorldBridge_GetTravelPeer(i, peer); i++)
        if (!strcmp(peer->name, sTravel.target)) break;
    if (strcmp(peer->name, sTravel.target) || !WorldBridge_GetTravelPeer(i, peer)) return "Your friend is no longer connected.";
    if (!peer->ready) return "Your friend is busy. Try again later.";
    flag = VisitedFlag(peer->group, peer->num);
    if (!flag) return "Your friend must be outside\nin a town or city.";
    if (!FlagGet(flag)) return "Visit that town yourself first.";
    if (!TravelStoryReady(peer->group, peer->num)) return "Finish the story event there\nbefore flying to a friend.";
    map = Overworld_GetMapHeaderByGroupAndId(peer->group, peer->num);
    if (!map || (map->mapType != MAP_TYPE_TOWN && map->mapType != MAP_TYPE_CITY)
        || !BuildLandingGrid(map, peer->group, peer->num, grid)) return "There is no safe place to land.";
    for (i = 1; i < NUM_HEAL_LOCATIONS; i++)
    {
        const struct HealLocation *heal = GetHealLocation(i);
        if (i == HEAL_LOCATION_EVER_GRANDE_CITY_POKEMON_LEAGUE && !FlagGet(FLAG_LANDMARK_POKEMON_LEAGUE)) continue;
        if (heal && (unsigned)heal->mapGroup == peer->group && (unsigned)heal->mapNum == peer->num
            && FindLanding(grid, map->mapLayout->width, map->mapLayout->height,
                heal->x, heal->y, peer->x, peer->y, x, y))
        {
            sTravel.flightHeal = i;
            return NULL;
        }
    }
    return "Ask your friend to move to\nopen ground near the Center.";
}

void WorldTravel_RequestMenu(void)
{
    if (sTravel.state == TRAVEL_IDLE && WorldBridge_Enabled()) sTravel.state = TRAVEL_REQUEST;
}

bool8 WorldTravel_OwnsFieldInput(void) { return sTravel.state != TRAVEL_IDLE; }

void WorldTravel_Update(void)
{
    s8 choice;
    if (sTravel.flightActive && !WorldTravel_NativeFlyRunning()) sTravel.flightActive = FALSE;
    if (sTravel.state == TRAVEL_IDLE) return;
    if (!TravelField())
    {
        /* A reset/scene replacement owns the new windows and lock. Never clear
         * its window using our previous numeric ID. */
        sTravel.window = WINDOW_NONE;
        sTravel.locked = FALSE;
        sTravel.state = TRAVEL_IDLE;
        return;
    }
    if (sTravel.state == TRAVEL_REQUEST)
    {
        if (ArePlayerFieldControlsLocked()) { sTravel.state = TRAVEL_IDLE; return; }
        sTravel.group = gSaveBlock1Ptr->location.mapGroup;
        sTravel.num = gSaveBlock1Ptr->location.mapNum;
        LockPlayerFieldControls();
        FreezeObjectEvents();
        sTravel.locked = TRUE;
        TravelFriends();
        return;
    }
    if (sTravel.group != (unsigned)gSaveBlock1Ptr->location.mapGroup
        || sTravel.num != (unsigned)gSaveBlock1Ptr->location.mapNum)
    {
        sTravel.window = WINDOW_NONE;
        sTravel.locked = FALSE;
        sTravel.state = TRAVEL_IDLE;
        return;
    }
    if (sTravel.delay) { sTravel.delay--; return; }
    if (sTravel.state == TRAVEL_MESSAGE)
    {
        if (gMain.newKeys & (A_BUTTON | B_BUTTON)) TravelFriends();
        return;
    }
    choice = Menu_ProcessInputNoWrap();
    if (choice == MENU_NOTHING_CHOSEN) return;
    if (sTravel.state == TRAVEL_FRIENDS)
    {
        if (choice >= 0 && sTravel.nextPage && (unsigned)choice == sTravel.count)
        { sTravel.page++; TravelFriends(); return; }
        if (choice >= 0 && sTravel.page && (unsigned)choice == sTravel.count + sTravel.nextPage)
        { sTravel.page--; TravelFriends(); return; }
        if (choice < 0 || (unsigned)choice >= sTravel.count) { WorldTravel_Close(); return; }
        strcpy(sTravel.target, sTravel.names[choice]);
        if (!TravelWindow()) return;
        TravelPrint(sTravel.target, 0);
        TravelPrint("Fly to this friend?", 24);
        TravelPrint("Fly", 48);
        TravelPrint("Cancel", 64);
        InitMenuNormal(sTravel.window, FONT_SMALL, 0, 48, 16, 2, 1);
        CopyWindowToVram(sTravel.window, COPYWIN_FULL);
        sTravel.state = TRAVEL_CONFIRM;
        sTravel.status = "Confirm Fly.";
    }
    else
    {
        struct WorldBridgePeer peer = {0};
        unsigned mon;
        s16 x, y;
        const char *error;
        if (choice != 0) { TravelFriends(); return; }
        error = TravelDestination(&peer, &mon, &x, &y);
        if (error) { TravelMessage(error); return; }
        WorldTravel_Close();
        if (!WorldTravel_StartNativeFly(peer.group, peer.num, x, y, mon))
        {
            LockPlayerFieldControls();
            FreezeObjectEvents();
            sTravel.locked = TRUE;
            TravelMessage("Fly is unavailable. Try again.");
            return;
        }
        sTravel.flightGroup = peer.group;
        sTravel.flightNum = peer.num;
        sTravel.flightActive = TRUE;
        sTravel.status = "Flying to friend.";
        sTravel.landingX = x; sTravel.landingY = y;
    }
}

void WorldTravel_WriteJSON(FILE *file)
{
    static const char *const phases[] = {"idle", "requested", "friends", "confirm", "message"};
    const char *p;
    fprintf(file, "{\"phase\":\"%s\",\"status\":\"", phases[sTravel.state]);
    for (p = sTravel.status; *p; p++)
        if (*p == '\n') fputs("\\n", file); else fputc(*p, file);
    fprintf(file, "\",\"target\":\"%s\",\"landing\":[%d,%d]}", sTravel.target, sTravel.landingX, sTravel.landingY);
}
#endif
