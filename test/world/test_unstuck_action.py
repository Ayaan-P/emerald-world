"""Execute the actual offline Unstuck action boundary with controlled engine stubs."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]

class UnstuckActionTests(unittest.TestCase):
    def test_game_ram_reset_retires_platform_unstuck_state(self):
        system=(ROOT/'src/platform/system.c').read_text()
        source=r'''
#include <assert.h>
#include <string.h>
typedef unsigned u32;
#define RESET_EWRAM 1
#define RESET_IWRAM 2
#define RESET_PALETTE 4
#define RESET_VRAM 8
#define RESET_OAM 16
#define RESET_SIO_REGS 32
#define RESET_SOUND_REGS 64
#define RESET_REGS 128
static char PLTT[4],VRAM_[4],OAM[4],REG_BASE[4];
static int cleared, reset;
static void ClearGameRam(void) {cleared++;}
static void WorldUnstuck_Reset(void) {reset++;}
''' + function(system,'RegisterRamReset') + r'''
int main(void) {
 RegisterRamReset(RESET_PALETTE);assert(!reset && !cleared);
 RegisterRamReset(RESET_EWRAM);assert(!reset && !cleared);
 RegisterRamReset(RESET_EWRAM|RESET_IWRAM);assert(reset==1 && cleared==1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='unstuck-reset-') as d:
            c,exe=Path(d)/'test.c',Path(d)/'test';c.write_text(source)
            p=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            subprocess.run([str(exe)],check=True,capture_output=True)

    def test_start_only_after_checks_and_return_to_origin_on_unsafe_arrival(self):
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <time.h>
#include <string.h>
typedef unsigned char bool8; typedef short s16; typedef unsigned char u8;
#define TRUE 1
#define FALSE 0
#define WARP_ID_NONE -1
#define NUM_TASKS 16
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
struct WorldUnstuckPlan { unsigned healId,originGroup,originNum,destinationGroup,destinationNum; s16 originX,originY,spawnX,spawnY,landingX,landingY; };
enum WorldUnstuckPlanResult { UNSTUCK_PLAN_OK,UNSTUCK_PLAN_BLOCKED,UNSTUCK_PLAN_NO_HEAL,UNSTUCK_PLAN_NO_LANDING };
enum WorldUnstuckUseResult { UNSTUCK_USE_STARTED,UNSTUCK_USE_ONLINE_UNSUPPORTED,UNSTUCK_USE_BLOCKED,UNSTUCK_USE_COOLDOWN,UNSTUCK_USE_STORAGE_ERROR };
enum NativeUnstuckResult { NATIVE_UNSTUCK_ALLOWED,NATIVE_UNSTUCK_COOLDOWN,NATIVE_UNSTUCK_STORAGE_ERROR,NATIVE_UNSTUCK_BAD_CLOCK };
struct Task { int isActive; } gTasks[NUM_TASKS];
static struct WorldUnstuckPlan sUnstuckPlan; static bool8 sUnstuckActive;
static int online, blocked, reserveResult, reservations, resets, transition, locks, freezes, effects, arrivalSafe=1;
static int warpGroup,warpNum,warpX,warpY;
static bool8 WorldBridge_Enabled(void) {return online;}
static enum WorldUnstuckPlanResult WorldUnstuck_Plan(struct WorldUnstuckPlan *p) {
 if(blocked) return UNSTUCK_PLAN_BLOCKED;
 *p=(struct WorldUnstuckPlan){.originGroup=1,.originNum=2,.originX=3,.originY=4,.destinationGroup=5,.destinationNum=6,.landingX=7,.landingY=8};return UNSTUCK_PLAN_OK;
}
static bool8 WorldUnstuck_ConservativelyBoxed(void) {return FALSE;}
static enum NativeUnstuckResult NativeUnstuck_ReserveCurrent(uint64_t now,int boxed,unsigned *r) {(void)now;(void)boxed;(void)r;reservations++;return reserveResult;}
static void Overworld_ResetStateAfterTeleport(void) {resets++;}
static void SetPlayerAvatarTransitionFlags(u8 f) {transition=f;}
static void LockPlayerFieldControls(void) {locks++;}
static void FreezeObjectEvents(void) {freezes++;}
static void FldEff_TeleportWarpOut(void) {effects++;}
static void SetWarpDestination(signed char group,signed char num,signed char warp,signed char x,signed char y) {(void)warp;warpGroup=group;warpNum=num;warpX=x;warpY=y;}
static bool8 WorldUnstuck_RevalidateArrival(const struct WorldUnstuckPlan *p,bool8 complete) {(void)p;return complete && arrivalSafe;}
'''
        code = (ROOT/'src/platform/world_unstuck.c').read_text()
        for name in ('WorldUnstuck_Reset','WorldUnstuck_Begin','WorldUnstuck_SetPlannedWarp','WorldUnstuck_CompleteArrival'):
            source += function(code,name)
        source += r'''
int main(void) {
 online=1;assert(WorldUnstuck_Begin()==UNSTUCK_USE_ONLINE_UNSUPPORTED && !reservations);online=0;
 blocked=1;assert(WorldUnstuck_Begin()==UNSTUCK_USE_BLOCKED && !reservations);blocked=0;
 for(int i=0;i<NUM_TASKS;i++)gTasks[i].isActive=1;
 assert(WorldUnstuck_Begin()==UNSTUCK_USE_BLOCKED && !reservations);gTasks[5].isActive=0;
 reserveResult=NATIVE_UNSTUCK_COOLDOWN;assert(WorldUnstuck_Begin()==UNSTUCK_USE_COOLDOWN && !effects);
 reserveResult=NATIVE_UNSTUCK_ALLOWED;assert(WorldUnstuck_Begin()==UNSTUCK_USE_STARTED);
 assert(resets==1 && transition==PLAYER_AVATAR_FLAG_ON_FOOT && locks==1 && freezes==1 && effects==1);
 assert(WorldUnstuck_SetPlannedWarp() && warpGroup==5 && warpNum==6 && warpX==7 && warpY==8);
 arrivalSafe=0;assert(WorldUnstuck_CompleteArrival());
 assert(warpGroup==1 && warpNum==2 && warpX==3 && warpY==4);
 assert(!WorldUnstuck_SetPlannedWarp());
 arrivalSafe=1;assert(WorldUnstuck_Begin()==UNSTUCK_USE_STARTED);
 assert(!WorldUnstuck_CompleteArrival() && !WorldUnstuck_SetPlannedWarp());
 assert(WorldUnstuck_Begin()==UNSTUCK_USE_STARTED);online=1;
 assert(WorldUnstuck_CompleteArrival() && warpGroup==1 && warpNum==2);online=0;
 assert(WorldUnstuck_Begin()==UNSTUCK_USE_STARTED); WorldUnstuck_Reset();
 assert(!WorldUnstuck_SetPlannedWarp() && !WorldUnstuck_CompleteArrival());
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='unstuck-action-') as d:
            c, exe = Path(d)/'test.c', Path(d)/'test'; c.write_text(source)
            p = subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            subprocess.run([str(exe)],check=True,capture_output=True)
