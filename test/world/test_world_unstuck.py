"""Execute real native unstuck destination policy with generated map data."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class WorldUnstuckTests(unittest.TestCase):
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
