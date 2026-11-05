"""Actual cave wire, bridge transition and native staging with fake transport."""
from pathlib import Path
from test_save_isolation import function
import hashlib, json, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
class NativeSharedCaveFlow(unittest.TestCase):
 def test_handshake_and_changed_world_return(self):
  groups=json.loads((ROOT/'data/maps/map_groups.json').read_text())
  group=groups['group_order'].index('gMapGroup_GeneratedWorld')
  a=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
  b=a.copy();b[2]=b[2][:2]+'#'+b[2][3:]
  ida=hashlib.sha256(b'EWGMAP01'+''.join(a).encode()).hexdigest()
  idb=hashlib.sha256(b'EWGMAP01'+''.join(b).encode()).hexdigest()
  bridge=(ROOT/'src/platform/world_bridge.c').read_text()
  helpers='\n'.join(function(bridge,name) for name in ('WorldBridge_GeneratedCaveReady','CaveLine','CavePump'))
  global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;} gMapHeader;\n'''
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
#include "platform/world_cave_wire.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
enum CaveState {CAVE_DISABLED,CAVE_IDLE,CAVE_WAIT,CAVE_WAIT_RESET,CAVE_ACK,CAVE_WAIT_OK,CAVE_READY,CAVE_MISMATCH,CAVE_RETURN_NONE};
static struct {bool8 connected,caveAvailable,staging,caveReturning;enum CaveState caveState;unsigned caveTimeout,caveRetry,snapshotAge;char caveExpected[65];struct WorldCaveWire caveWire;size_t outputSize;char output[4096];} sWorld;
static char sent[4096];static int leaving,disconnected;
static struct WarpData destination;
const char *LinkTransport_TagPeer(void){return 0;}
const void *LinkTransport_PendingTag(void){return 0;}
const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};
int WorldRally_HasReturn(void){return 0;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return 1;}
int Platform_ReloadGeneratedMap(void){return 1;}
int IsMapTypeOutdoors(int x){return x==1;}int TestPlayerAvatarFlags(int f){return f==1;}
void PlayerGetDestCoords(s16 *x,s16 *y){*x=15;*y=16;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int z,s8 g,s8 n,s8 w,s8 x,s8 y){(void)z;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){leaving++;}
static bool8 Ready(void){return TRUE;}
static void Flush(void){memcpy(sent,sWorld.output,sWorld.outputSize);sent[sWorld.outputSize]=0;sWorld.outputSize=0;}
static void Disconnect(void){disconnected=1;sWorld.connected=0;}
''' +helpers+r'''
static void deliver(const char *id, int changed){
 char *begin[]={"CAVE","BEGIN",(char *)id};char *end[]={"CAVE","END",(char *)id};
 char row[32],idx[4];char *parts[]={"CAVE","ROW",(char *)id,idx,row};
 assert(CaveLine(3,begin));
 for(int y=0;y<31;y++){
  for(int x=0;x<31;x++)row[x]=(x==0||y==0||x==30||y==30||(changed&&x==2&&y==2))?'#':'.';
  row[31]=0;snprintf(idx,sizeof(idx),"%d",y);assert(CaveLine(5,parts));
 }
 assert(CaveLine(3,end));
}
int main(void){
 const char *a="ID_A",*b="ID_B";struct MapLayout base={19,26,0,0,0,0};
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;save.location=(struct WarpData){3,4,0,8,9};
 save.dynamicWarp=(struct WarpData){7,8,0,10,11};sWorld.connected=1;sWorld.caveAvailable=1;sWorld.caveState=CAVE_IDLE;
 CavePump();assert(!strcmp(sent,"CAVE GET\n") && sWorld.caveState==CAVE_WAIT);
 deliver(a,0);assert(sWorld.caveState==CAVE_ACK && !WorldBridge_GeneratedCaveReady());
 CavePump();assert(!strncmp(sent,"CAVE ACK ",9) && sWorld.caveState==CAVE_WAIT_OK);
 char *ok[]={"CAVE","OK",(char *)a};assert(CaveLine(3,ok) && WorldBridge_GeneratedCaveReady());
 sWorld.snapshotAge=181;assert(!WorldBridge_GeneratedCaveReady()&&!GeneratedMap_CanEnter());sWorld.snapshotAge=0;
 assert(GeneratedMap_CanEnter()&&GeneratedMap_Enter());save.location=destination;
 const struct MapLayout *map=GeneratedMap_ResolveLayout(&base);assert(map->map[2*31+2]==0x3333);
 /* A different authority after reconnect must not change the live map or
  * publish cave presence; it sends the player back before acknowledging. */
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(b,1);
 assert(sWorld.caveState==CAVE_MISMATCH&&!WorldBridge_GeneratedCaveReady());
 assert(map->map[2*31+2]==0x3333);CavePump();assert(sWorld.caveReturning && leaving==2);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_WAIT_OK && !WorldBridge_GeneratedCaveReady());
 char *ok2[]={"CAVE","OK",(char *)b};assert(CaveLine(3,ok2)&&WorldBridge_GeneratedCaveReady());
 assert(GeneratedMap_Enter());save.location=destination;map=GeneratedMap_ResolveLayout(&base);
 assert(map->map[2*31+2]==0x0722 && !disconnected);
 /* Exhausted warp tasks must not mark a failed return as in progress. */
 for(int i=0;i<16;i++)gTasks[i].isActive=1;
 int before=leaving;assert(!GeneratedMap_Leave()&&leaving==before);
 for(int i=0;i<16;i++)gTasks[i].isActive=0;
 /* If a reconnecting authority has no generated cave, leave rather than
  * publish the old instance or silently install a different world. */
 sWorld.caveState=CAVE_WAIT;char *none[]={"CAVE","NONE"};
 assert(CaveLine(2,none)&&sWorld.caveState==CAVE_RETURN_NONE&&!WorldBridge_GeneratedCaveReady());
 CavePump();assert(sWorld.caveReturning);save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_DISABLED&&!WorldBridge_GeneratedCaveReady());
 /* A reconnect during the entry fade must not acknowledge a different map
  * just because the engine has not switched its current map ID yet. */
 sWorld.caveState=CAVE_READY;assert(GeneratedMap_Enter());assert(GeneratedMap_EntryPending());
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(a,0);
 assert(sWorld.caveState==CAVE_MISMATCH&&!WorldBridge_GeneratedCaveReady());
 before=leaving;CavePump();assert(leaving==before&&GeneratedMap_EntryPending());
 save.location=destination;GeneratedMap_ResolveLayout(&base);assert(!GeneratedMap_EntryPending());
 CavePump();assert(sWorld.caveReturning&&leaving==before+1);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_WAIT_OK&&!WorldBridge_GeneratedCaveReady());
 char *ok3[]={"CAVE","OK",(char *)a};assert(CaveLine(3,ok3)&&WorldBridge_GeneratedCaveReady());
 assert(GeneratedMap_Enter()&&GeneratedMap_EntryPending());sWorld.caveState=CAVE_WAIT;
 assert(CaveLine(2,none)&&sWorld.caveState==CAVE_RETURN_NONE);before=leaving;CavePump();
 assert(leaving==before&&GeneratedMap_EntryPending());save.location=destination;GeneratedMap_ResolveLayout(&base);
 CavePump();assert(sWorld.caveReturning);save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_DISABLED);
 for(int i=0;i<16;i++)gTasks[i].isActive=1;
 assert(!GeneratedMap_CanEnter());for(int i=0;i<16;i++)gTasks[i].isActive=0;
 /* A live authority replacement during entry invalidates the old ACK and
  * cannot publish mismatched geometry while the old warp is still pending. */
 sWorld.caveState=CAVE_READY;assert(GeneratedMap_Enter()&&GeneratedMap_EntryPending());
 char *reset[]={"CAVE","RESET",(char *)b};assert(CaveLine(3,reset)&&sWorld.caveState==CAVE_IDLE);
 assert(!WorldBridge_GeneratedCaveReady());CavePump();assert(!strcmp(sent,"CAVE GET\n"));
 deliver(b,1);assert(sWorld.caveState==CAVE_MISMATCH);before=leaving;CavePump();assert(leaving==before);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();assert(sWorld.caveReturning);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);
 assert(CaveLine(3,ok2)&&WorldBridge_GeneratedCaveReady());
 char *badreset[]={"CAVE","RESET","BAD"};assert(!CaveLine(3,badreset));
 /* A reset can overtake an outstanding GET: accept its new-map response
  * without sending a duplicate, or retry after a bounded wait. */
 sWorld.caveState=CAVE_WAIT;sWorld.caveTimeout=600;assert(CaveLine(3,reset));
 assert(sWorld.caveState==CAVE_WAIT_RESET);deliver(b,1);assert(sWorld.caveState==CAVE_ACK);
 CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);assert(CaveLine(3,ok2));
 sWorld.caveState=CAVE_WAIT;sWorld.caveTimeout=600;assert(CaveLine(3,reset));
 for(int i=0;i<60;i++)CavePump();
 assert(sWorld.caveState==CAVE_WAIT&&!strcmp(sent,"CAVE GET\n"));
 return 0;
}'''.replace('ID_A',ida).replace('ID_B',idb)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
   for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
    (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void SetWarpDestination(s8,s8,s8,s8,s8);void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void PlayerGetDestCoords(s16*,s16*);void StoreInitialPlayerAvatarState(void);void DoWarp(void);\n#define MAP_OFFSET 7\n')
   (p/'task.h').write_text('struct Task {int isActive;}; extern struct Task gTasks[16];\n#define NUM_TASKS 16\n')
   (p/'platform/world_rally.h').write_text('struct WorldRallySnapshot{unsigned id;}; int WorldRally_HasReturn(void); int WorldRally_GetSnapshot(struct WorldRallySnapshot *);\n')
   (p/'platform/link_transport.h').write_text('const char *LinkTransport_TagPeer(void); const void *LinkTransport_PendingTag(void); const void *LinkTransport_PendingInvitation(void);\n')
   (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void);int WorldBridge_GeneratedCaveReady(void);\n')
   for name in ('generated_map.h','world_cave_wire.h'):(p/'platform'/name).write_text((ROOT/'include/platform'/name).read_text())
   (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
   (p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
