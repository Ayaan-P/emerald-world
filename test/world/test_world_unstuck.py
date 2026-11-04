"""Execute real native unstuck destination policy with generated map data."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class WorldUnstuckTests(unittest.TestCase):
    def test_landing_search_rejects_blocked_or_isolated_tiles_without_mutation(self):
        source = r'''
#include <assert.h>
#include <string.h>
#include "src/platform/unstuck_landing.c"
int main(void) {
 u8 plain[25], clear[25], before[25]; s16 x=-1,y=-1;
 memset(plain,1,sizeof(plain)); memset(clear,1,sizeof(clear));
 memcpy(before,clear,sizeof(clear));
 assert(Unstuck_SelectLanding(plain,clear,5,5,2,2,&x,&y) && x==2 && y==2);
 assert(!memcmp(before,clear,sizeof(clear)));
 clear[12]=0; x=y=-1;
 assert(Unstuck_SelectLanding(plain,clear,5,5,2,2,&x,&y));
 assert(!(x==2 && y==2) && clear[x+y*5]);
 memset(clear,0,sizeof(clear)); clear[0]=1; clear[1]=1; x=y=-1;
 assert(!Unstuck_SelectLanding(plain,clear,5,5,2,2,&x,&y) && x==-1 && y==-1);
 memset(clear,1,sizeof(clear)); plain[12]=0;
 assert(!Unstuck_SelectLanding(plain,clear,5,5,2,2,&x,&y));
 assert(!Unstuck_SelectLanding(plain,clear,129,1,0,0,&x,&y));
 assert(!Unstuck_SelectLanding(plain,clear,5,5,2,2,NULL,&y));
 return 0;
}
'''
        self.compile_and_run(source)

    def test_loaded_grid_rejects_hazards_and_actual_occupied_tiles(self):
        source = r'''
#include <assert.h>
#include <string.h>
#include "src/platform/world_unstuck.c"
struct MapHeader gMapHeader;
struct BackupMapLayout gBackupMapLayout;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
struct SaveBlock1 *gSaveBlock1Ptr;
struct Main gMain;
void CB2_Overworld(void) {}
static int blockedX=-1, blockedY=-1, specialX=-1, specialY=-1;
u8 MapGridGetCollisionAt(s32 x,s32 y) { return x==blockedX && y==blockedY; }
u8 MapGridGetElevationAt(s32 x,s32 y) { (void)x;(void)y;return ELEVATION_DEFAULT; }
s32 MapGridGetMetatileBehaviorAt(s32 x,s32 y) { return x==specialX && y==specialY ? 1 : MB_NORMAL; }
bool8 FlagGet(u16 flag) { (void)flag;return FALSE; }
int main(void) {
 static u16 map[400]; static struct SaveBlock1 save; u8 plain[25], clear[25];
 gSaveBlock1Ptr=&save; gMain.callback2=CB2_Overworld;
 struct MapLayout layout={.width=5,.height=5};
 struct WarpEvent warp={.x=1,.y=1};
 struct CoordEvent coord={.x=2,.y=1};
 struct ObjectEventTemplate npc={.x=3,.y=1,.movementRangeX=1,.movementRangeY=0};
 struct MapEvents events={.warpCount=1,.warps=&warp,.coordEventCount=1,.coordEvents=&coord,.objectEventCount=1,.objectEvents=&npc};
 gMapHeader.mapLayout=&layout; gMapHeader.events=&events;
 gBackupMapLayout.width=20; gBackupMapLayout.height=19; gBackupMapLayout.map=map;
 memset(plain,77,sizeof(plain)); memset(clear,77,sizeof(clear));
 gMain.callback2=NULL; assert(!WorldUnstuck_BuildLoadedGrid(plain,clear,25));
 assert(plain[0]==77 && clear[0]==77); gMain.callback2=CB2_Overworld;
 assert(!WorldUnstuck_BuildLoadedGrid(plain,clear,24)); assert(plain[0]==77 && clear[0]==77);
 blockedX=7;blockedY=7;specialX=8;specialY=7;
 gObjectEvents[0].active=1; gObjectEvents[0].isPlayer=1; gObjectEvents[0].currentCoords.x=9;gObjectEvents[0].currentCoords.y=9;
 gObjectEvents[1].active=1; gObjectEvents[1].currentCoords.x=10;gObjectEvents[1].currentCoords.y=9;
 assert(WorldUnstuck_BuildLoadedGrid(plain,clear,25));
 assert(!plain[0] && !plain[1]); /* collision, non-normal */
 assert(!plain[1+1*5] && !plain[2+1*5] && !plain[3+1*5]); /* events and NPC range */
 assert(plain[2+2*5] && clear[2+2*5]); /* own player excluded */
 assert(plain[3+2*5] && !clear[3+2*5]); /* other live object */
 assert(!WorldUnstuck_BuildLoadedGrid(plain,plain,25));
 return 0;
}
'''
        self.compile_and_run(source)

    def test_departure_and_story_gates_fail_closed(self):
        source = r'''
#include <assert.h>
#include "src/platform/world_unstuck.c"
struct SaveBlock1 *gSaveBlock1Ptr;
struct Main gMain;
struct PaletteFadeControl gPaletteFade;
struct PlayerAvatar gPlayerAvatar;
struct MapHeader gMapHeader;
u8 gWirelessCommType;
static int havePokemon=1, nativeActive, activityOwns, scriptActive, specialArea, flyAllowed=1, league, cleared;
static u16 city, sky;
void CB1_Overworld(void) {}
void CB2_Overworld(void) {}
int NativeLink_IsActive(void) { return nativeActive; }
int WorldActivity_OwnsFieldInput(void) { return activityOwns; }
bool8 ScriptContext_IsEnabled(void) { return scriptActive; }
bool32 GetSafariZoneFlag(void) { return specialArea; }
bool8 InBattlePike(void) { return specialArea; }
u8 CurrentBattlePyramidLocation(void) { return specialArea ? 1 : PYRAMID_LOCATION_NONE; }
bool8 InMultiPartnerRoom(void) { return specialArea; }
bool8 Overworld_MapTypeAllowsTeleportAndFly(u8 t) { (void)t;return flyAllowed; }
bool8 FlagGet(u16 flag) { if (flag==FLAG_SYS_POKEMON_GET) return havePokemon; if (flag==FLAG_LANDMARK_POKEMON_LEAGUE) return league; if (flag==FLAG_SYS_GAME_CLEAR) return cleared; return 0; }
u16 VarGet(u16 var) { return var==VAR_SOOTOPOLIS_CITY_STATE ? city : sky; }
int main(void) {
 static struct SaveBlock1 save;
 gSaveBlock1Ptr=&save; gMain.callback1=CB1_Overworld; gMain.callback2=CB2_Overworld;
 gMapHeader.mapType=MAP_TYPE_ROUTE; assert(WorldUnstuck_AllowedDeparture());
 havePokemon=0; assert(!WorldUnstuck_AllowedDeparture()); havePokemon=1;
 nativeActive=1; assert(!WorldUnstuck_AllowedDeparture()); nativeActive=0;
 activityOwns=1; assert(!WorldUnstuck_AllowedDeparture()); activityOwns=0;
 scriptActive=1; assert(!WorldUnstuck_AllowedDeparture()); scriptActive=0;
 gMain.inBattle=1; assert(!WorldUnstuck_AllowedDeparture()); gMain.inBattle=0;
 gPaletteFade.active=1; assert(!WorldUnstuck_AllowedDeparture()); gPaletteFade.active=0;
 gWirelessCommType=1; assert(!WorldUnstuck_AllowedDeparture()); gWirelessCommType=0;
 specialArea=1; assert(!WorldUnstuck_AllowedDeparture()); specialArea=0;
 gMapHeader.mapType=MAP_TYPE_UNDERWATER; assert(!WorldUnstuck_AllowedDeparture());
 gMapHeader.mapType=MAP_TYPE_INDOOR; flyAllowed=0; assert(!WorldUnstuck_AllowedDeparture());
 gMapHeader.allowEscaping=1; assert(WorldUnstuck_AllowedDeparture());
 assert(!WorldUnstuck_StoryAllowsDestination(0));
 assert(!WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_SOUTHERN_ISLAND_EXTERIOR));
 assert(WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_SOOTOPOLIS_CITY));
 city=1; assert(!WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_SOOTOPOLIS_CITY)); city=6;
 sky=1; assert(!WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_SOOTOPOLIS_CITY)); sky=3;
 assert(WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_SOOTOPOLIS_CITY));
 assert(!WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_EVER_GRANDE_CITY_POKEMON_LEAGUE)); league=1;
 assert(WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_EVER_GRANDE_CITY_POKEMON_LEAGUE));
 assert(!WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_BATTLE_FRONTIER_OUTSIDE_EAST)); cleared=1;
 assert(WorldUnstuck_StoryAllowsDestination(HEAL_LOCATION_BATTLE_FRONTIER_OUTSIDE_EAST));
 return 0;
}
'''
        self.compile_and_run(source)

    def test_boxed_check_is_conservative_and_has_no_movement_side_effects(self):
        source = r'''
#include <assert.h>
#include "src/platform/world_unstuck.c"
struct PlayerAvatar gPlayerAvatar;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
static u8 collision=COLLISION_IMPASSABLE, ledge, behavior;
void MoveCoords(u8 d,s16 *x,s16 *y) { if(d==DIR_SOUTH)(*y)++; if(d==DIR_NORTH)(*y)--; if(d==DIR_WEST)(*x)--; if(d==DIR_EAST)(*x)++; }
u8 GetCollisionAtCoords(struct ObjectEvent *o,s16 x,s16 y,u32 d) { (void)o;(void)x;(void)y;(void)d;return collision; }
u8 GetLedgeJumpDirection(s16 x,s16 y,u8 d) { (void)x;(void)y;(void)d;return ledge; }
s32 MapGridGetMetatileBehaviorAt(s32 x,s32 y) { (void)x;(void)y;return behavior; }
bool8 MetatileBehavior_IsSurfableFishableWater(u8 b) { return b==1; }
bool8 MetatileBehavior_IsWarpDoor(u8 b) { return b==2; }
bool8 MetatileBehavior_IsNonAnimDoor(u8 b) { return b==3; }
int main(void) {
 gPlayerAvatar.objectEventId=0; gObjectEvents[0].active=1; gObjectEvents[0].isPlayer=1;
 assert(WorldUnstuck_ConservativelyBoxed());
 collision=COLLISION_NONE; assert(!WorldUnstuck_ConservativelyBoxed());
 collision=COLLISION_OBJECT_EVENT; assert(!WorldUnstuck_ConservativelyBoxed());
 collision=COLLISION_IMPASSABLE; ledge=DIR_SOUTH; assert(!WorldUnstuck_ConservativelyBoxed()); ledge=0;
 for(behavior=1;behavior<=3;behavior++) assert(!WorldUnstuck_ConservativelyBoxed());
 behavior=0; gObjectEvents[0].active=0; assert(!WorldUnstuck_ConservativelyBoxed());
 return 0;
}
'''
        self.compile_and_run(source)

    def compile_and_run(self, source):
        with tempfile.TemporaryDirectory(prefix='unstuck-policy-') as d:
            c, exe = Path(d)/'test.c', Path(d)/'test'; c.write_text(source)
            p = subprocess.run(['cc','-std=gnu99','-DPORTABLE','-DMODERN=1','-DVER_64BIT','-Wall','-Wextra','-Werror','-Wno-ignored-qualifiers','-ffunction-sections','-fdata-sections','-iquote',str(ROOT),'-iquote',str(ROOT/'include'),str(c),'-Wl,--gc-sections','-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            subprocess.run([str(exe)],check=True,capture_output=True)

    def test_whitelist_checks_exact_last_heal_location_and_never_mutates_it(self):
        source = r'''
#include <assert.h>
#include <string.h>
#include "src/heal_location.c"
#include "src/platform/world_unstuck.c"
int main(void) {
    const struct HealLocation *center = GetHealLocation(HEAL_LOCATION_OLDALE_TOWN);
    struct WarpData warp = { center->mapGroup, center->mapNum, WARP_ID_NONE, center->x, center->y }, before = warp;
    assert(WorldUnstuck_HealDestination(&warp, MALE) == HEAL_LOCATION_OLDALE_TOWN);
    assert(!memcmp(&warp, &before, sizeof(warp)));
    warp.x++; assert(!WorldUnstuck_HealDestination(&warp, MALE)); warp.x--;
    warp.warpId=0; assert(!WorldUnstuck_HealDestination(&warp, MALE)); warp.warpId=WARP_ID_NONE;
    warp.mapGroup=-1; assert(!WorldUnstuck_HealDestination(&warp, MALE));
    const struct HealLocation *island = GetHealLocation(HEAL_LOCATION_SOUTHERN_ISLAND_EXTERIOR);
    warp = (struct WarpData){island->mapGroup,island->mapNum,WARP_ID_NONE,island->x,island->y};
    assert(!WorldUnstuck_HealDestination(&warp, MALE));
    const struct HealLocation *home = GetHealLocation(HEAL_LOCATION_LITTLEROOT_TOWN_MAYS_HOUSE_2F);
    warp = (struct WarpData){home->mapGroup,home->mapNum,WARP_ID_NONE,home->x,home->y};
    assert(!WorldUnstuck_HealDestination(&warp, MALE));
    assert(WorldUnstuck_HealDestination(&warp, FEMALE) == HEAL_LOCATION_LITTLEROOT_TOWN_MAYS_HOUSE_2F);
    assert(!WorldUnstuck_HealDestination(&warp, 99));
    assert(!WorldUnstuck_HealDestination(NULL, MALE));
    return 0;
}
'''
        self.compile_and_run(source)
