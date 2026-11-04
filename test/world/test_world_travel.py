"""Execute native travel policy and geometry, not source assertions."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class WorldTravelTests(unittest.TestCase):
    def run_c(self, body, unit='world_travel'):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'travel.c'
            binary = pathlib.Path(directory) / 'travel'
            source.write_text('#include <assert.h>\n#include <stdlib.h>\n#include "src/platform/' + unit + '.c"\n' + body)
            result = subprocess.run([
                'gcc', '-std=gnu99', '-DPORTABLE', '-DMODERN=1', '-DNONMATCHING',
                '-DUBFIX', '-DVER_64BIT', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-ignored-qualifiers',
                '-ffunction-sections', '-fdata-sections', '-iquote', '.', '-iquote', 'include',
                str(source), '-Wl,--gc-sections', '-o', str(binary),
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)

    def test_travel_is_blocked_during_battle_link_and_activity_handoffs(self):
        self.run_c(r'''
struct SaveBlock1 *gSaveBlock1Ptr;
struct Main gMain;
struct PaletteFadeControl gPaletteFade;
struct PlayerAvatar gPlayerAvatar;
u8 gWirelessCommType;
static int nativeActive, activityOwns, scriptActive;
void CB1_Overworld(void) {}
void CB2_Overworld(void) {}
int NativeLink_IsActive(void) { return nativeActive; }
int WorldActivity_OwnsFieldInput(void) { return activityOwns; }
bool8 ScriptContext_IsEnabled(void) { return scriptActive; }
int main(void) {
    static struct SaveBlock1 save;
    gSaveBlock1Ptr = &save;
    gMain.callback1 = CB1_Overworld; gMain.callback2 = CB2_Overworld;
    assert(TravelField());
    nativeActive = 1; assert(!TravelField()); nativeActive = 0;
    activityOwns = 1; assert(!TravelField()); activityOwns = 0;
    scriptActive = 1; assert(!TravelField()); scriptActive = 0;
    gMain.inBattle = 1; assert(!TravelField()); gMain.inBattle = 0;
    gPaletteFade.active = 1; assert(!TravelField()); gPaletteFade.active = 0;
    gWirelessCommType = 1; assert(!TravelField()); gWirelessCommType = 0;
    gPlayerAvatar.tileTransitionState = 1; assert(!TravelField());
    return 0;
}
''')

    def test_fly_task_capacity_accounts_for_native_nested_effects(self):
        self.run_c(r'''
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#include "src/task.c"
#pragma GCC diagnostic pop
static void busy(u8 id) { (void)id; }
int main(void) {
    ResetTasks();
    assert(WorldTravel_CanAllocateFly());
    for (unsigned i = 0; i < NUM_TASKS - 3; i++) CreateTask(busy, 0);
    assert(WorldTravel_CanAllocateFly());
    CreateTask(busy, 0);
    assert(!WorldTravel_CanAllocateFly());
    CreateTask(busy, 0);
    CreateTask(busy, 0);
    assert(!WorldTravel_CanAllocateFly());
    assert(gTasks[0].func == busy);
    return 0;
}
''')

    def test_sootopolis_scripted_arrivals_keep_their_private_story_gate(self):
        self.run_c(r'''
#include "src/event_data.c"
struct SaveBlock1 *gSaveBlock1Ptr;
u16 *const gSpecialVars[] = {NULL};
int main(void) {
    static struct SaveBlock1 save;
    unsigned g = MAP_GROUP(MAP_SOOTOPOLIS_CITY), n = MAP_NUM(MAP_SOOTOPOLIS_CITY);
    gSaveBlock1Ptr = &save;
    assert(TravelStoryReady(g, n));
    for (unsigned i = 1; i <= 5; i++) {
        VarSet(VAR_SOOTOPOLIS_CITY_STATE, i);
        assert(!TravelStoryReady(g, n));
    }
    VarSet(VAR_SOOTOPOLIS_CITY_STATE, 6);
    assert(TravelStoryReady(g, n));
    VarSet(VAR_SKY_PILLAR_STATE, 1);
    assert(!TravelStoryReady(g, n));
    VarSet(VAR_SKY_PILLAR_STATE, 3);
    assert(TravelStoryReady(g, n));
    assert(TravelStoryReady(MAP_GROUP(MAP_OLDALE_TOWN), MAP_NUM(MAP_OLDALE_TOWN)));
    return 0;
}
''')

    def test_late_peer_changes_use_normal_fly_fallback_without_save_writes(self):
        self.run_c(r'''
#include "src/platform/world_bridge.c"
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#include "src/fieldmap.c"
#pragma GCC diagnostic pop
#include "src/event_data.c"
struct SaveBlock1 *gSaveBlock1Ptr;
struct PlayerAvatar gPlayerAvatar;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
int main(void) {
    static struct SaveBlock1 save, before;
    static u16 map[40 * 40];
    struct MapEvents events = {0};
    u16 attributes[512] = {0};
    struct Tileset tiles = { .metatileAttributes = attributes };
    struct MapLayout layout = { .primaryTileset = &tiles, .secondaryTileset = &tiles };
    gSaveBlock1Ptr = &save;
    save.location.mapGroup = MAP_GROUP(MAP_LITTLEROOT_TOWN);
    save.location.mapNum = MAP_NUM(MAP_LITTLEROOT_TOWN);
    save.pos.x = 5; save.pos.y = 5;
    gBackupMapLayout.map = map;
    gBackupMapLayout.width = gBackupMapLayout.height = 40;
    gMapHeader.events = &events;
    gMapHeader.mapLayout = &layout;
    for (unsigned i = 0; i < 40 * 40; i++) map[i] = PACK_ELEVATION(ELEVATION_DEFAULT);
    sWorld.connected = 1; sWorld.live.peerCount = 1;
    strcpy(sWorld.live.peers[0].id, "friend");
    sWorld.live.peers[0].group = save.location.mapGroup;
    sWorld.live.peers[0].num = save.location.mapNum;
    sWorld.live.peers[0].x = 6; sWorld.live.peers[0].y = 5;
    sWorld.live.peers[0].ready = 1;
    strcpy(sTravel.target, "friend");
    sTravel.flightGroup = save.location.mapGroup;
    sTravel.flightNum = save.location.mapNum;
    sTravel.flightHeal = HEAL_LOCATION_LITTLEROOT_TOWN_BRENDANS_HOUSE;
    before = save;
    sTravel.flightActive = 1;
    assert(!WorldTravel_ArrivalFallback());
    sTravel.flightActive = 1;
    sWorld.live.peers[0].ready = 0;
    assert(WorldTravel_ArrivalFallback() == sTravel.flightHeal);
    assert(!sTravel.flightActive);
    sWorld.live.peers[0].ready = 1;
    sWorld.live.peers[0].x = 5; /* now occupies the chosen landing */
    sTravel.flightActive = 1;
    assert(WorldTravel_ArrivalFallback() == sTravel.flightHeal);
    sWorld.live.peers[0].x = 6;
    map[12 + 12 * 40] |= MAPGRID_IMPASSABLE;
    sTravel.flightActive = 1;
    assert(WorldTravel_ArrivalFallback() == sTravel.flightHeal);
    assert(!memcmp(&before, &save, sizeof(save)));
    return 0;
}
''')

    def test_only_native_fly_towns_have_private_visited_gates(self):
        self.run_c(r'''
int main(void) {
    assert(VisitedFlag(MAP_GROUP(MAP_LITTLEROOT_TOWN), MAP_NUM(MAP_LITTLEROOT_TOWN)) == FLAG_VISITED_LITTLEROOT_TOWN);
    assert(VisitedFlag(MAP_GROUP(MAP_FORTREE_CITY), MAP_NUM(MAP_FORTREE_CITY)) == FLAG_VISITED_FORTREE_CITY);
    assert(VisitedFlag(MAP_GROUP(MAP_SOOTOPOLIS_CITY), MAP_NUM(MAP_SOOTOPOLIS_CITY)) == FLAG_VISITED_SOOTOPOLIS_CITY);
    assert(VisitedFlag(MAP_GROUP(MAP_EVER_GRANDE_CITY), MAP_NUM(MAP_EVER_GRANDE_CITY)) == FLAG_VISITED_EVER_GRANDE_CITY);
    assert(!VisitedFlag(MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)));
    assert(!VisitedFlag(MAP_GROUP(MAP_OLDALE_TOWN_POKEMON_CENTER_1F), MAP_NUM(MAP_OLDALE_TOWN_POKEMON_CENTER_1F)));
    assert(!VisitedFlag(0xffffffff, 0xffffffff));
    return 0;
}
''')

    def test_floor_rejects_water_collision_elevation_and_script_behaviors(self):
        self.run_c(r'''
int main(void) {
    assert(SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT), MB_NORMAL));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT) | MAPGRID_IMPASSABLE, MB_NORMAL));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_SURF), MB_NORMAL));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_MULTI_LEVEL), MB_NORMAL));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT), MB_POND_WATER));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT), MB_ANIMATED_DOOR));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT), MB_JUMP_SOUTH));
    assert(!SafeFloor(PACK_ELEVATION(ELEVATION_DEFAULT), MB_TALL_GRASS));
    return 0;
}
''')

    def test_native_event_flags_and_moving_npc_ranges_block_landing(self):
        self.run_c(r'''
#include "src/event_data.c"
struct SaveBlock1 *gSaveBlock1Ptr;
int main(void) {
    static struct SaveBlock1 save;
    struct ObjectEventTemplate npc = { .x = 3, .y = 3, .movementRangeX = 1, .movementRangeY = 1, .flagId = FLAG_HIDE_LITTLEROOT_TOWN_BIRCHS_LAB_BIRCH };
    struct WarpEvent warp = { .x = 1, .y = 2 };
    struct CoordEvent script = { .x = 2, .y = 1 };
    struct MapEvents events = { .objectEventCount = 1, .objectEvents = &npc,
        .warpCount = 1, .warps = &warp, .coordEventCount = 1, .coordEvents = &script };
    gSaveBlock1Ptr = &save;
    assert(BlockedByEvents(&events, 1, 2));
    assert(BlockedByEvents(&events, 2, 1));
    assert(BlockedByEvents(&events, 3, 3));
    assert(BlockedByEvents(&events, 4, 4));
    assert(!BlockedByEvents(&events, 5, 5));
    FlagSet(npc.flagId);
    assert(!BlockedByEvents(&events, 3, 3));
    assert(BlockedByEvents(&events, 1, 2));
    npc.flagId = 0;
    assert(BlockedByEvents(&events, 3, 3));
    return 0;
}
''')

    def test_destination_grid_uses_native_geometry_and_committed_occupancy(self):
        self.run_c(r'''
#include "src/platform/world_bridge.c"
#include "src/event_data.c"
struct SaveBlock1 *gSaveBlock1Ptr;
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#include "src/fieldmap.c"
#pragma GCC diagnostic pop
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
int main(void) {
    u16 blocks[25], attrs[512] = {0};
    u8 grid[25];
    struct Tileset tiles = { .metatileAttributes = attrs };
    struct MapLayout layout = { .width = 5, .height = 5, .map = blocks,
        .primaryTileset = &tiles, .secondaryTileset = &tiles };
    struct MapEvents events = {0};
    struct MapHeader map = { .mapLayout = &layout, .events = &events };
    unsigned group = MAP_GROUP(MAP_LITTLEROOT_TOWN), num = MAP_NUM(MAP_LITTLEROOT_TOWN);
    for (unsigned i = 0; i < 25; i++) blocks[i] = PACK_ELEVATION(ELEVATION_DEFAULT);
    sWorld.connected = 1;
    sWorld.live.peerCount = 1;
    strcpy(sWorld.live.peers[0].id, "friend");
    sWorld.live.peers[0].group = group; sWorld.live.peers[0].num = num;
    sWorld.live.peers[0].x = 3; sWorld.live.peers[0].y = 3;
    attrs[1] = MB_POND_WATER;
    blocks[1] |= 1;
    blocks[2] |= MAPGRID_IMPASSABLE;
    blocks[3] = PACK_ELEVATION(ELEVATION_SURF);
    sWorld.live.tileCount = 1;
    sWorld.live.tiles[0] = (struct Tile){group, num, 4, 4, 0, 0};
    assert(BuildLandingGrid(&map, group, num, grid));
    assert(grid[0] && grid[4]);
    assert(!grid[1] && !grid[2] && !grid[3]);
    assert(!grid[3 + 3 * 5] && !grid[4 + 4 * 5]);
    layout.width = 129;
    assert(!BuildLandingGrid(&map, group, num, grid));
    return 0;
}
''')

    def test_bridge_exposes_only_fresh_committed_human_peers(self):
        self.run_c(r'''
int main(void) {
    struct WorldBridgePeer peer;
    sWorld.enabled = sWorld.connected = 1;
    sWorld.live.peerCount = 2;
    strcpy(sWorld.live.peers[0].id, "@npc");
    strcpy(sWorld.live.peers[1].id, "friend");
    sWorld.live.peers[1].group = 0;
    sWorld.live.peers[1].num = 9;
    sWorld.live.peers[1].x = 5;
    sWorld.live.peers[1].y = 6;
    sWorld.live.peers[1].ready = 1;
    assert(WorldBridge_GetPeer(0, &peer));
    assert(!strcmp(peer.name, "friend") && peer.ready && peer.x == 5 && peer.y == 6);
    assert(!WorldBridge_GetPeer(1, &peer));
    assert(!WorldBridge_TravelTileClear(0, 9, 5, 6));
    assert(WorldBridge_TravelTileClear(0, 9, 4, 6));
    sWorld.live.tileCount = 1;
    sWorld.live.tiles[0] = (struct Tile){0, 9, 4, 6, 0, 0};
    assert(!WorldBridge_TravelTileClear(0, 9, 4, 6));
    sWorld.snapshotAge = 181;
    assert(!WorldBridge_GetPeer(0, &peer));
    assert(!WorldBridge_TravelTileClear(0, 9, 4, 5));
    sWorld.snapshotAge = 0;
    sWorld.connected = 0;
    assert(!WorldBridge_GetPeer(0, &peer));
    assert(!WorldBridge_TravelTileClear(0, 9, 4, 5));
    return 0;
}
''', unit='world_bridge')

    def test_landing_is_adjacent_reachable_and_never_a_blocked_tile(self):
        self.run_c(r'''
int main(void) {
    u8 grid[25];
    s16 x = -1, y = -1;
    memset(grid, 1, sizeof(grid));
    grid[2 + 2 * 5] = 0; /* friend occupies this tile */
    assert(FindLanding(grid, 5, 5, 0, 0, 2, 2, &x, &y));
    assert(abs(x - 2) + abs(y - 2) == 1);
    assert(grid[x + y * 5] == 1);
    /* A wall divides the safe Fly point from the friend. */
    for (unsigned i = 0; i < 5; i++) grid[1 + i * 5] = 0;
    assert(!FindLanding(grid, 5, 5, 0, 0, 3, 2, &x, &y));
    memset(grid, 1, sizeof(grid));
    grid[0] = 0;
    assert(!FindLanding(grid, 5, 5, 0, 0, 2, 2, &x, &y));
    assert(!FindLanding(grid, 5, 5, 5, 0, 2, 2, &x, &y));
    assert(!FindLanding(grid, 5, 5, 0, 0, -1, 2, &x, &y));
    assert(!FindLanding(grid, 129, 1, 0, 0, 2, 0, &x, &y));
    assert(!FindLanding(grid, 0, 5, 0, 0, 2, 2, &x, &y));
    memset(grid, 0, sizeof(grid));
    grid[0] = 1;
    assert(!FindLanding(grid, 5, 5, 0, 0, 2, 2, &x, &y));
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
