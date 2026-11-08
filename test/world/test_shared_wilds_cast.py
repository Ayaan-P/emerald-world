from native_party_fixture import write_party_fixture
from pathlib import Path
import hashlib, json, subprocess, tempfile, unittest
from test_save_isolation import function
from test_large_generated_cave import DOC
from test_shared_generated_cave import MemoryAuthority
from world import cave_blueprint,wilds_cast
from world.shared_cave import SharedCave,CaveError
ROOT=Path(__file__).resolve().parents[2]
class SharedWildsCast(unittest.TestCase):
    def blob(self,text='Welcome, traveler!'):
        return wilds_cast.encode(cave_blueprint.proposal_from_blueprint(DOC,side=63),[{'gfx':7,'text':text},{'gfx':8,'text':'Second!'}])
    def test_authority_identity_visibility_npc_collision_and_persistence(self):
        blob=self.blob();area=SharedCave(blob);self.assertEqual(area.version,8)
        self.assertEqual(area.identity,hashlib.sha256(blob).hexdigest());self.assertFalse(area.walkable(2,1));self.assertTrue(area.walkable(1,2))
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
            try:
                server._replace_cave(blob,label='Guided islands')
                def connect(name,suffix):
                    ident=server.create_identity(name);c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
                    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLY%s'%(name,ident['token'],suffix)).encode());self.assertIn(b'WELCOME 1',c['out']);c['out'].clear();return c
                a=connect('Alice','CAVE8');b=connect('Bob','CAVE8');old=connect('Old','CAVE7')
                for c in (a,b):
                    server._line(c,b'CAVE GET');self.assertEqual(c['out'].decode(),area.frames());c['out'].clear()
                    server._line(c,('CAVE ACK '+area.identity).encode());self.assertIn(b'CAVE OK',c['out']);c['out'].clear()
                server._line(old,b'CAVE GET');self.assertEqual(old['out'],b'CAVE NONE\n');old['out'].clear()
                g,n=server.wilds_map
                for c,x,y in ((a,1,1),(b,1,2)):
                    server._line(c,(f'STATE 1 {g} {n} {x} {y} 1 7 1 '+('a'*16)+' '+('b'*16)).encode());self.assertFalse(c['closing'])
                self.assertIn('PEER Bob ',server._snapshot(a));self.assertNotIn('PEER Bob ',server._snapshot(old))
                with self.assertRaises(ValueError):server._replace_cave(self.blob('Hello, friend!'))
                server._line(a,(f'STATE 2 {g} {n} 2 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode());self.assertTrue(a['closing'])
            finally:server.close()
            restored=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True)
            try:
                self.assertEqual(restored.shared_cave.identity,area.identity);self.assertEqual(restored.list_generated_areas()[0]['kind'],'wilds')
            finally:restored.close()
        for bad in (blob[:-1],blob+b'x',blob[:8]+b'\x09'+blob[9:],blob[:10]+b'\x01'+blob[11:]):
            with self.assertRaises(CaveError):SharedCave(bad)

    def test_real_c_wire_v8_and_tampering(self):
        code=r'''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[512];struct WorldCaveWire w={0};int r=0;
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;
line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;
r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}
return r==1 && w.version==8 && w.nextRow==63 && w.cast[0]==2 ? 0 : 3;}'''
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
            build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
            area=SharedCave(self.blob());frames=area.frames();run=lambda x:subprocess.run([str(p/'test')],input=x,capture_output=True,text=True).returncode
            self.assertEqual(run(frames),0)
            guide=f'CAVE CAST {area.identity} {area.cast.hex()}\n'
            for bad in (frames.replace(guide,''),frames.replace(guide,guide+guide),frames.replace(area.cast.hex(),'ff'+area.cast.hex()[2:]),frames.replace(' CAST\n',' WILDS\n',1)):
                self.assertNotEqual(run(bad),0)


    def test_native_cast_reconnect_and_dialogue_only_replacement(self):
        groups=json.loads((ROOT/'data/maps/map_groups.json').read_text())
        group=groups['group_order'].index('gMapGroup_GeneratedWorld')
        rows=['#'*63]+['#'+'.'*61+'#']*61+['#'*63]
        cells=''.join(rows).encode('ascii')
        text_a=b'Welcome!';text_b=b'Hello, friend!'
        guide_a=bytes([2,7,2,1,len(text_a)])+text_a.ljust(57,b'\0')+bytes([8,20,20,7])+b'Second!'.ljust(57,b'\0')+bytes(61)
        guide_b=bytes([2,8,2,1,len(text_b)])+text_b.ljust(57,b'\0')+bytes([8,20,20,7])+b'Second!'.ljust(57,b'\0')+bytes(61)
        ida=hashlib.sha256(b'EWGMAP08'+guide_a+cells).hexdigest()
        idb=hashlib.sha256(b'EWGMAP08'+guide_b+cells).hexdigest()
        bridge=(ROOT/'src/platform/world_bridge.c').read_text()
        helpers='\n'.join(function(bridge,name) for name in ('WorldBridge_GeneratedCaveReady','CaveLine','CavePump','IsGeneratedCaveMap','MapCoords'))
        global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\n#define OBJECT_EVENT_TEMPLATES_COUNT 64\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nstruct ObjectEventTemplate {u8 localId,graphicsId,kind;s16 x,y;u8 elevation,movementType;u16 trainerType,trainerRange_berryTreeId;const u8 *script;u16 flagId;};\nstruct MapEvents {u8 objectEventCount,warpCount,coordEventCount,bgEventCount;const struct ObjectEventTemplate *objectEvents;const void *warps,*coordEvents,*bgEvents;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;const struct MapEvents *events;} gMapHeader;\n'''
        code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
#include "platform/world_cave_wire.h"
#include "constants/maps.h"
#include "wild_encounter.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
enum CaveState {CAVE_DISABLED,CAVE_IDLE,CAVE_WAIT,CAVE_WAIT_RESET,CAVE_ACK,CAVE_WAIT_OK,CAVE_READY,CAVE_MISMATCH,CAVE_RETURN_NONE};
static struct {bool8 connected,caveAvailable,staging,caveReturning,caveV2Probe,caveV3Probe,caveV4Probe,caveV5Probe,caveV6Probe,caveV7Probe,caveV8Probe;enum CaveState caveState;unsigned caveTimeout,caveRetry,snapshotAge;char caveExpected[65];struct WorldCaveWire caveWire;size_t outputSize;char output[4096];} sWorld;
static int leaving,disconnected;static struct WarpData destination;static struct MapEvents events;
const u8 GeneratedWorld_Wilds_EventScript_Guide[]={0};const u8 GeneratedWorld_Wilds_EventScript_Cast2[]={0},GeneratedWorld_Wilds_EventScript_Cast3[]={0};extern u8 gGeneratedWildsGuideText[58];
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
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){leaving++;}
static bool8 Ready(void){return TRUE;}
static int WorldCatalog_Coords(unsigned g,unsigned n,unsigned x,unsigned y){(void)g;(void)n;(void)x;(void)y;return 0;}
static void Flush(void){sWorld.outputSize=0;}
static void Disconnect(void){disconnected=1;sWorld.connected=0;}
''' + helpers + r'''
static void deliver(const char *id,char *guide){
 char *begin[]={"CAVE","BEGIN",(char *)id,"CAST"};char *meta[]={"CAVE","CAST",(char *)id,guide};char *end[]={"CAVE","END",(char *)id};
 char row[64],idx[4];char *parts[]={"CAVE","ROW",(char *)id,idx,row};
 assert(CaveLine(4,begin));assert(CaveLine(4,meta));
 for(int y=0;y<63;y++){
  for(int x=0;x<63;x++)row[x]=(x==0||y==0||x==62||y==62)?'#':'.';
  row[63]=0;snprintf(idx,sizeof(idx),"%d",y);assert(CaveLine(5,parts));
 }
 assert(CaveLine(3,end));
}
int main(void){const char *a="ID_A",*b="ID_B";struct MapLayout base={19,26,0,0,0,0};
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;gMapHeader.events=&events;save.location=(struct WarpData){3,4,0,8,9};
 sWorld.connected=1;sWorld.caveAvailable=1;sWorld.caveV2Probe=1;sWorld.caveV3Probe=1;sWorld.caveV4Probe=1;sWorld.caveV5Probe=1;sWorld.caveV6Probe=1;sWorld.caveV7Probe=1;sWorld.caveV8Probe=1;sWorld.caveState=CAVE_WAIT;
 deliver(a,"META_A_SENTINEL");assert(sWorld.caveState==CAVE_ACK);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);
 char *ok[]={"CAVE","OK",(char*)a};assert(CaveLine(3,ok));
 extern u8 gPlayerPartyCount;gPlayerPartyCount=0;assert(!GeneratedMap_Enter());gPlayerPartyCount=1;assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(save.location.mapNum==1);assert(gMapHeader.events->objectEventCount==2 && gMapHeader.events->objectEvents[0].graphicsId==7);assert(gGeneratedWildsGuideText[0]==0xd1);assert(!GeneratedMap_SharedCoordValid(2,1));assert(!GeneratedMap_SharedCoordValid(20,20));assert(GeneratedMap_SharedCoordValid(40,40));assert(MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_WILDS),MAP_NUM(MAP_GENERATED_WORLD_WILDS),61,61));assert(!MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_CAVE),MAP_NUM(MAP_GENERATED_WORLD_CAVE),61,61));assert(GeneratedMap_SharedCoordValid(61,61));assert(!GeneratedMap_SharedCoordValid(63,61));assert(GeneratedMap_MatchesPreparedCastWilds(sWorld.caveWire.cast,WORLD_CAVE_CAST_BYTES,sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));assert(!GeneratedMap_MatchesPreparedWilds(sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));assert(!GeneratedMap_MatchesPreparedLarge(sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));
 /* Reconnect to the same identity without evicting a player already inside. */
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(a,"META_A_SENTINEL");
 assert(sWorld.caveState==CAVE_ACK);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);assert(CaveLine(3,ok));
 /* Same geometry with a different ecology is a different identity. It must
    leave the old cave before staging or acknowledging the replacement. */
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(b,"META_B_SENTINEL");
 assert(sWorld.caveState==CAVE_MISMATCH && gGeneratedWildsGuideText[0]==0xd1);
 CavePump();assert(sWorld.caveReturning && leaving==2);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_WAIT_OK);char *ok2[]={"CAVE","OK",(char*)b};assert(CaveLine(3,ok2));
 assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(gMapHeader.events->objectEvents[0].graphicsId==8 && gGeneratedWildsGuideText[0]==0xc2 && !disconnected);
 /* An unsupported profile response must not be accepted without v2 negotiation. */
 sWorld.caveState=CAVE_WAIT;sWorld.caveV2Probe=0;WorldCaveWire_Reset(&sWorld.caveWire);
 char *bad[]={"CAVE","BEGIN",(char*)a,"1"};assert(!CaveLine(4,bad));
 sWorld.caveV2Probe=1;sWorld.caveV6Probe=0;WorldCaveWire_Reset(&sWorld.caveWire);
 char *unadvertised[]={"CAVE","BEGIN",(char*)a,"WILDS"};assert(!CaveLine(4,unadvertised));
 /* Legacy clients receiving NONE after an in-flight reset return safely. */
 sWorld.caveState=CAVE_WAIT_RESET;char *none[]={"CAVE","NONE"};
 assert(CaveLine(2,none)&&sWorld.caveState==CAVE_RETURN_NONE);
 return 0;}
'''.replace('ID_A',ida).replace('ID_B',idb).replace('META_A_SENTINEL',guide_a.hex()).replace('META_B_SENTINEL',guide_b.hex())
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
            for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
                (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void SetWarpDestination(s8,s8,s8,s8,s8);void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void PlayerGetDestCoords(s16*,s16*);void StoreInitialPlayerAvatarState(void);void DoWarp(void);\n#define MAP_OFFSET 7\n')
            (p/'task.h').write_text('struct Task {int isActive;}; extern struct Task gTasks[16];\n#define NUM_TASKS 16\n')
            (p/'platform/world_rally.h').write_text('struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void);int WorldRally_GetSnapshot(struct WorldRallySnapshot *);\n')
            (p/'platform/link_transport.h').write_text('const char *LinkTransport_TagPeer(void);const void *LinkTransport_PendingTag(void);const void *LinkTransport_PendingInvitation(void);\n')
            (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void);int WorldBridge_GeneratedCaveReady(void);\n')
            for name in ('generated_map.h','world_cave_wire.h'):(p/'platform'/name).write_text((ROOT/'include/platform'/name).read_text())
            (p/'constants/event_object_movement.h').write_text('#define MOVEMENT_TYPE_FACE_LEFT 9\n')
            (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GENERATED_WORLD_WILDS (({group}<<8)|1)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
            (p/'wild_encounter.h').write_text('#include "global.h"\nstruct WildPokemon {u8 minLevel,maxLevel;u16 species;};struct WildPokemonInfo {u8 encounterRate;const struct WildPokemon *wildPokemon;};\n')
            (p/'constants/species.h').write_text('#define SPECIES_EGG 412\n#define SPECIES_OLD_UNOWN_B 252\n#define SPECIES_OLD_UNOWN_Z 276\n')
            (p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
            cmd.insert(-2,str(write_party_fixture(p)))
            build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)




    def test_native_negotiates_v8_then_older_protocols(self):
        src=(ROOT/'src/platform/world_bridge.c').read_text()
        code=r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_CAVE_PROFILES 1
#define GENERATED_CAVE_WILDLIFE 1
#define GENERATED_MAP_LARGE 1
#define GENERATED_MAP_WILDS 1
#define GENERATED_WILDS_GUIDE 1
#define GENERATED_WILDS_CAST 1
static struct {bool8 rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,caveProbe,caveLegacy,caveV2Probe,caveV2Legacy,caveV3Probe,caveV3Legacy,caveV4Probe,caveV4Legacy,caveV5Probe,caveV5Legacy,caveV6Probe,caveV6Legacy,caveV7Probe,caveV7Legacy,caveV8Probe,caveV8Legacy;char trainer[25],token[65],output[4096];int outputSize;} sWorld;
''' + function(src,'CaveProbeRejected') + function(src,'QueueHello') + r'''
int main(void){char *err[]={"ERROR","AUTH"};strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");
QueueHello(0);assert(strstr(sWorld.output,"CAVE8\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV8Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE7\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV7Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE6\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV6Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE5\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV5Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE4\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV4Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE3\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV3Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE2\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV2Legacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveLegacy);
QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLY\n"));return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'test.c',Path(tmp)/'test';c.write_text(code)
            build=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)



