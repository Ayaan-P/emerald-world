"""Outer reference-engine components consume actual authority wire frames.

The fixture stubs field task/warp execution. It does not compile the separately
pinned RC10 Expansion engine or establish graphical playthrough acceptance.
"""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from native_party_fixture import write_party_fixture
from test_save_isolation import function
from test_shared_generated_cave import MemoryAuthority, BLOB

ROOT=Path(__file__).resolve().parents[2]

GLOBAL=r'''
#ifndef G
#define G
#include <stdint.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define PLAYER_AVAR 1
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
struct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};
struct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};
struct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};
extern struct Save *gSaveBlock1Ptr;
extern struct {u32 vblankCounter1;} gMain;
extern struct {int mapType;struct MapLayout *mapLayout;} gMapHeader;
#endif
'''

PRELUDE=r'''
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
#include "platform/world_cave_wire.h"
#include "pokemon.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
enum CaveState {CAVE_DISABLED,CAVE_IDLE,CAVE_WAIT,CAVE_WAIT_RESET,CAVE_ACK,CAVE_WAIT_OK,CAVE_READY,CAVE_MISMATCH,CAVE_RETURN_NONE};
static struct {
 bool8 connected,caveAvailable,staging,caveReturning,caveProbe,caveLegacy;
 bool8 regionProbe,regionLegacy,regionAvailable,regionSelected;
 bool8 rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,commandsProbe,commandsLegacy,chatAvailable,fieldKnown;
 bool8 exploreAvailable;
 unsigned exploreProbeSeq;
 enum CaveState caveState;
 unsigned caveTimeout,caveRetry,snapshotAge,regionPhase,regionTimeout,seq;
 char caveExpected[65],regionRequest[42],trainer[25],token[65];
 const char *regionStatus;
 struct WorldCaveWire caveWire;
 size_t outputSize;char output[4096];
 struct {char chatStatus[12];unsigned commandMask;} live;
} sWorld;
static int freeField,warps,disconnected,stateReports;
static char sent[4096];
static struct WarpData destination;
const char *LinkTransport_TagPeer(void){return 0;}
const void *LinkTransport_PendingTag(void){return 0;}
const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};
int WorldRally_HasReturn(void){return 0;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return 1;}int Platform_ReloadGeneratedMap(void){return 1;}
int IsMapTypeOutdoors(int x){return x==1;}int TestPlayerAvatarFlags(int f){return f==1;}
void PlayerGetDestCoords(s16 *x,s16 *y){*x=15;*y=16;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int z,s8 g,s8 n,s8 w,s8 x,s8 y){(void)z;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){warps++;}
static bool8 Ready(void){return freeField;}static bool8 PresenceReady(void){return freeField;}
static void Flush(void){strcpy(sent,sWorld.output);sWorld.outputSize=0;}
static void Disconnect(void){disconnected++;sWorld.connected=0;}
static void SendState(void){stateReports++;}
'''

MAIN=r'''
static unsigned split(char *line,char **parts){unsigned n=0;char *s=strtok(line," \n");while(s){assert(n<8);parts[n++]=s;s=strtok(NULL," \n");}return n;}
int main(void){char place[42],line[256],revision[65];struct MapLayout base={19,26,0,0,0,0};char *parts[8];unsigned n;
 assert(fgets(place,sizeof(place),stdin));assert(strlen(place)==41);assert(getchar()=='\n');
 assert(fgets(revision,sizeof(revision),stdin));assert(strlen(revision)==64);assert(getchar()=='\n');
 strcpy(sWorld.trainer,"Alice");strcpy(sWorld.token,"token");sWorld.commandsLegacy=1;QueueHello(0);
 assert(strstr(sWorld.output,"CAVEREGION1\n"));char *auth[]={"ERROR","AUTH"};
 assert(CaveProbeRejected(2,auth));assert(sWorld.regionLegacy&&!sWorld.caveLegacy);
 sWorld.commandsLegacy=1;QueueHello(0);assert(strstr(sWorld.output,"CAVE\n")&&!strstr(sWorld.output,"REGION1"));
 sWorld.regionLegacy=0;sWorld.commandsLegacy=1;QueueHello(0);sWorld.outputSize=0;
 sWorld.connected=1;sWorld.caveAvailable=1;sWorld.chatAvailable=1;sWorld.caveState=CAVE_READY;sWorld.fieldKnown=1;
 char *ready[]={"REGION","READY","1"};assert(RegionLine(3,ready));
 assert(!RegionQueue("area:bad"));
 snprintf(line,sizeof(line),"/region %s",place);assert(WorldBridge_ChatSend("*",line));
 assert(!WorldBridge_GeneratedCaveReady());assert(!RegionQueue(place));
 RegionPump();assert(!stateReports&&sWorld.regionPhase==1); /* Chat still owns field. */
 freeField=1;RegionPump();assert(stateReports==1&&sWorld.regionPhase==2);
 RegionPump();assert(sWorld.regionPhase==3&&strstr(sent,"REGION SELECT area:"));
 assert(warps==0);
 char *unsolicited[]={"REGION","SELECTED","area:00000000-0000-0000-0000-000000000000",revision};
 assert(!RegionLine(4,unsolicited));
 assert(fgets(line,sizeof(line),stdin));n=split(line,parts);assert(RegionLine(n,parts));
 assert(sWorld.caveState==CAVE_IDLE&&!sWorld.regionPhase);CavePump();assert(!strcmp(sent,"CAVE GET\n"));
 while(fgets(line,sizeof(line),stdin)){n=split(line,parts);assert(n&&CaveLine(n,parts));if(n==3&&!strcmp(parts[1],"END"))break;}
 assert(sWorld.caveState==CAVE_ACK&&!WorldBridge_GeneratedCaveReady());CavePump();
 assert(strstr(sent,"CAVE ACK "));char *ok[]={"CAVE","OK",revision};assert(CaveLine(3,ok));
 assert(WorldBridge_GeneratedCaveReady()&&warps==0);
 assert(!strcmp(WorldBridge_ChatStatus(),"region ready: use WORLD"));
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;save.location=(struct WarpData){3,4,0,8,9};
 gPlayerPartyCount=0;assert(!GeneratedMap_Enter());gPlayerPartyCount=1;
 assert(GeneratedMap_Enter());save.location=destination;assert(GeneratedMap_ResolveLayout(&base)->width==31);
 assert(!RegionQueue(place));assert(GeneratedMap_Leave());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(save.location.mapGroup==3&&save.location.mapNum==4&&save.location.x==8&&save.location.y==9);
 assert(warps==2);
 assert(RegionQueue(place));RegionPump();RegionPump();char *refused[]={"REGION","REFUSED"};assert(RegionLine(2,refused));
 assert(WorldBridge_GeneratedCaveReady());assert(!strcmp(WorldBridge_ChatStatus(),"region refused"));
 assert(RegionQueue(place));sWorld.regionTimeout=1;RegionPump();assert(!disconnected&&!sWorld.regionPhase);
 assert(RegionQueue(place));RegionPump();RegionPump();sWorld.regionTimeout=1;RegionPump();assert(disconnected==1);
 return 0;}
'''


class NativeRegions(unittest.TestCase):
    def test_outer_bridge_capability_fallback_keeps_cohort(self):
        source=(ROOT/'src/platform/world_bridge.c').read_text()
        flags=('GENERATED_WORLD_REGIONS','GENERATED_MAP_READY','GENERATED_CAVE_PROFILES',
               'GENERATED_CAVE_WILDLIFE','GENERATED_MAP_LARGE','GENERATED_MAP_WILDS',
               'GENERATED_WILDS_GUIDE','GENERATED_WILDS_CAST','GENERATED_WILDS_EVENTS',
               'GENERATED_WILDS_SHARED_TERRAIN','GENERATED_WILDS_SHARED_GEOMETRY',
               'GENERATED_WILDS_LARGE_TERRAIN','GENERATED_WORLD_XL')
        fields=['commandsProbe','commandsLegacy','caveProbe','caveLegacy','regionProbe','regionLegacy','rallyProbe','rallyLegacy',
                'travelProbe','travelLegacy','chatProbe','chatLegacy']
        fields += ['caveV'+version+suffix for version in ('2','3','4','5','6','7','8','9','9T','9G','9H','10') for suffix in ('Probe','Legacy')]
        code='#include <assert.h>\n#include <stdio.h>\n#include <string.h>\ntypedef int bool8;\n#define TRUE 1\n#define FALSE 0\n'
        code+=''.join('#define '+flag+' 1\n' for flag in flags)
        code+='static struct {bool8 '+','.join(fields)+';char trainer[25],token[65],output[4096];int outputSize;} sWorld;\n'
        code+=function(source,'CaveProbeRejected')+function(source,'QueueHello')
        code+='\nint main(void){char *error[]={"ERROR","AUTH"};strcpy(sWorld.trainer,"Alice");strcpy(sWorld.token,"token");\nsWorld.commandsLegacy=1;QueueHello(0);assert(strstr(sWorld.output,"CAVE10REGION1\\n"));\nassert(CaveProbeRejected(2,error));assert(sWorld.regionLegacy&&!sWorld.caveV10Legacy);\nsWorld.commandsLegacy=1;QueueHello(0);assert(strstr(sWorld.output,"CAVE10\\n")&&!strstr(sWorld.output,"REGION1"));return 0;}\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(code)
            build=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_native_selection_admission_and_manual_entry_preserve_return(self):
        source=(ROOT/'src/platform/world_bridge.c').read_text()
        names=('Identifier','WorldBridge_GeneratedCaveReady','CaveProbeRejected','CaveLine','CavePump',
               'QueueHello','RegionIdentifier','RegionQueue','RegionLine','RegionPump','WorldBridge_ChatCommandAllowed','WorldBridge_ChatSend','WorldBridge_ChatStatus')
        code=(ROOT/'include/platform/chat_command_gate.h').read_text()+PRELUDE+'\n'.join(function(source,name) for name in names)+MAIN
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text(GLOBAL)
            for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
                (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void SetWarpDestination(s8,s8,s8,s8,s8);void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void PlayerGetDestCoords(s16*,s16*);void StoreInitialPlayerAvatarState(void);void DoWarp(void);\n#define MAP_OFFSET 7\n')
            (p/'task.h').write_text('struct Task{int isActive;};extern struct Task gTasks[16];\n#define NUM_TASKS 16\n')
            (p/'platform/world_rally.h').write_text('struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void);int WorldRally_GetSnapshot(struct WorldRallySnapshot*);\n')
            (p/'platform/link_transport.h').write_text('const void *LinkTransport_PendingTag(void);const void *LinkTransport_PendingInvitation(void);\n')
            (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void);int WorldBridge_GeneratedCaveReady(void);\n')
            (p/'platform/generated_map.h').write_text((ROOT/'include/platform/generated_map.h').read_text())
            (p/'constants/maps.h').write_text('#define MAP_GENERATED_WORLD_CAVE (31<<8)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
            (p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_WORLD_REGIONS=1','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/generated_map.c'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),str(write_party_fixture(p)),'-o',str(p/'test')]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True)
            try:
                for index in range(2):
                    blob=bytearray(BLOB)
                    if index:blob[8+2*31+2]=ord('#')
                    revision=server._replace_cave(bytes(blob));region=server.open_region(revision)
                    identity=server.create_identity('Alice'+str(index))
                    peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
                    def send(line):
                        peer['out'].clear();server._line(peer,line.encode());return bytes(peer['out'])
                    send('HELLO 1 '+identity['id']+' '+identity['token']+' SOCIALCAVEREGION1')
                    send('STATE 1 0 9 8 8 1 7 1 '+'a'*16+' '+'b'*16)
                    selected=send('REGION SELECT '+region['place_id']);frames=send('CAVE GET')
                    wire=(region['place_id']+'\n'+revision+'\n').encode()+selected+frames
                    run=subprocess.run([str(p/'test')],input=wire,capture_output=True)
                    self.assertEqual(run.returncode,0,run.stderr.decode())
            finally:server.close()


if __name__=='__main__':unittest.main()
