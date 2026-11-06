"""Connected, durable owner-authored geometry using in-memory authority."""
import hashlib,json,subprocess,tempfile,threading,unittest
from test_save_isolation import function
from pathlib import Path
from unittest.mock import patch
from test_large_generated_cave import DOC
from test_shared_generated_cave import MemoryAuthority
from world import wilds_events,shared_terrain,shared_terrain_control
from world.shared_cave import SharedCave
ROOT=Path(__file__).resolve().parents[2]

class SharedAgentGeometry(unittest.TestCase):
 def blob(self):
  return wilds_events.compile_document({'blueprint':DOC,'cast':[{'gfx':7,'text':'Hi!'}], 'events':{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Hi!'}]}})
 def positions(self,area):
  reserved={(1,1),(61,60),(61,61),(2,1)}
  opening=next((x,y) for x in range(1,62) for y in range(1,62) if (x,y) not in reserved and area._rows[y][x]==ord('#') and any(area.walkable(nx,ny) for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))))
  for x in range(1,62):
   for y in range(1,62):
    if (x,y) in reserved or not area.walkable(x,y):continue
    try:shared_terrain.encode(area,{opening:0,(x,y):2});return opening,(x,y)
    except ValueError:pass
  self.fail('no connected geometry example')
 def test_geometry_reachable_empty_gate_compatibility_and_restart(self):
  blob=self.blob();area=SharedCave(blob);identity=area.identity;opening,water=self.positions(area)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);ident=server.create_identity('Alice');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9G'%(ident['id'],ident['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
    g,n=server.wilds_map;server._line(c,(f'STATE 1 {g} {n} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode());c['out'].clear()
    edits=[{'x':opening[0],'y':opening[1],'terrain':'grass'},{'x':water[0],'y':water[1],'terrain':'water'}]
    with self.assertRaises(ValueError):server.set_shared_geometry(identity,edits)
    c['in_generated_cave']=False;c['state']=[0,0,0,0,1,7,0]
    def owner(_socket,request,**kwargs):
     admin={'id':None,'out':bytearray(),'closing':False,'sock':object()};server._admin_line(admin,json.dumps(request).encode());return json.loads(admin['out'])
    with patch('world.shared_terrain_control.admin_request',side_effect=owner):result=shared_terrain_control.publish_geometry(p/'owner',identity,edits)
    self.assertTrue(result['ok']);self.assertEqual(result['revision'],1);self.assertIn(b'CAVE RESET',c['out']);self.assertIsNone(c['cave_ack'])
    self.assertTrue(server._active_walkable(*opening));self.assertFalse(server._active_walkable(*water));view=server.inspect_shared_terrain(identity)
    self.assertEqual(view['effective_rows'][opening[1]][opening[0]],'.');self.assertEqual(view['effective_rows'][water[1]][water[0]],'#')
    with self.assertRaises(ValueError):server.set_shared_geometry(identity,[{'x':1,'y':2,'terrain':'water'}])
    c['out'].clear();c['cave_next']=0;server._line(c,b'CAVE GET');self.assertIn(b'CAVE TERRAIN',c['out']);c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
    server._line(c,(f'STATE 2 {g} {n} {opening[0]} {opening[1]} 1 7 1 '+('a'*16)+' '+('b'*16)).encode());self.assertFalse(c['closing'])
    old=server.create_identity('Old');o={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(o,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(old['id'],old['token'])).encode());o['out'].clear();server._line(o,b'CAVE GET');self.assertEqual(o['out'],b'CAVE NONE\n')
   finally:server.close()
   restored=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True)
   try:self.assertTrue(restored._active_walkable(*opening));self.assertFalse(restored._active_walkable(*water))
   finally:restored.close()

 def test_agent_can_remove_and_replace_overlay_without_losing_revision(self):
  blob=self.blob();area=SharedCave(blob);identity=area.identity;opening,water=self.positions(area)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);edits=[{'x':opening[0],'y':opening[1],'terrain':'grass'},{'x':water[0],'y':water[1],'terrain':'water'}]
    self.assertEqual(server.set_shared_geometry(identity,edits)['revision'],1)
    result=server.set_shared_geometry(identity,[{'x':opening[0],'y':opening[1],'terrain':'original'}]);self.assertEqual(result['revision'],2);self.assertFalse(server._active_walkable(*opening));self.assertFalse(server._active_walkable(*water))
    result=server.set_shared_geometry(identity,[],replace=True);self.assertEqual(result['revision'],3);self.assertEqual(server._active_terrain(),(3,b'\0'));self.assertFalse(server._active_walkable(*opening));self.assertTrue(server._active_walkable(*water))
    self.assertFalse(server.set_shared_geometry(identity,[],replace=True)['changed'])
    old=server.create_identity('Old');o={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(o,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(old['id'],old['token'])).encode());o['out'].clear();server._line(o,b'CAVE GET');self.assertEqual(o['out'],b'CAVE NONE\n')
    newer=server.create_identity('New');g={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(g,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9G'%(newer['id'],newer['token'])).encode());g['out'].clear();server._line(g,b'CAVE GET');self.assertIn(f'CAVE TERRAIN {identity} 3 00\n'.encode(),g['out'])
   finally:server.close()
   restored=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True)
   try:self.assertEqual(restored._active_terrain(),(3,b'\0'));self.assertFalse(restored._active_walkable(*opening));self.assertTrue(restored._active_walkable(*water))
   finally:restored.close()
 def test_cli_can_replace_or_clear_geometry(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'patch.json';p.write_text('[]')
   with patch('world.shared_terrain_control.admin_request',return_value={'ok':True}) as send,patch('builtins.print'):
    self.assertEqual(shared_terrain_control.main(['--admin-socket','/tmp/owner','--area','a'*64,'--geometry','--replace','--tiles-file',str(p)]),0)
    self.assertEqual(send.call_args.args[1],{'command':'set_shared_geometry','identity':'a'*64,'tiles':[],'replace':True})
    with patch('sys.stderr'),self.assertRaises(SystemExit):shared_terrain_control.main(['--admin-socket','/tmp/owner','--area','a'*64,'--replace','--tiles-file',str(p)])
 def test_geometry_cannot_isolate_characters(self):
  blob=wilds_events.compile_document({'blueprint':DOC,'cast':[{'gfx':7,'text':'Hi!'}, {'gfx':8,'text':'Hi!'}], 'events':{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Hi!'}]}});area=SharedCave(blob)
  with self.assertRaises(ValueError):shared_terrain.encode(area,{(19,20):2,(20,19):2,(20,21):2,(21,20):2})
 def test_geometry_and_entry_are_serialized(self):
  blob=self.blob();area=SharedCave(blob);identity=area.identity;opening,_=self.positions(area)
  for _ in range(8):
   with tempfile.TemporaryDirectory() as t:
    p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
    try:
     server._replace_cave(blob);ident=server.create_identity('Alice');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
     server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9G'%(ident['id'],ident['token'])).encode());c['out'].clear()
     server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
     g,n=server.wilds_map;barrier=threading.Barrier(2);result=[]
     def edit():
      barrier.wait()
      try:server.set_shared_geometry(identity,[{'x':opening[0],'y':opening[1],'terrain':'grass'}]);result.append('edited')
      except ValueError:result.append('blocked')
     def enter():
      barrier.wait();server._line(c,(f'STATE 1 {g} {n} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode())
     a=threading.Thread(target=edit);b=threading.Thread(target=enter);a.start();b.start();a.join();b.join()
     if result==['edited']:self.assertFalse(c.get('in_generated_cave',False));self.assertIsNone(c.get('cave_ack'))
     else:self.assertEqual(result,['blocked']);self.assertTrue(c.get('in_generated_cave'));self.assertEqual(server._active_terrain()[0],0)
    finally:server.close()
 def test_native_stages_connected_geometry_and_rejects_live_collision_change(self):
     groups=json.loads((ROOT/'data/maps/map_groups.json').read_text())
     group=groups['group_order'].index('gMapGroup_GeneratedWorld')
     rows=['#'*63]+['#'+('.'*9+'#'+'.'*51 if y==10 else '.'*61)+'#' for y in range(1,62)]+['#'*63]
     cells=''.join(rows).encode('ascii')
     text_a=b'Welcome!';text_b=b'Hello, friend!'
     guide_a=bytes([2,7,2,1,len(text_a)])+text_a.ljust(57,b'\0')+bytes([8,20,20,7])+b'Second!'.ljust(57,b'\0')+bytes(61)
     guide_b=guide_a
     graph_a=bytes([0,1,0,1,1,6])+b'Hello!'.ljust(57,b'\0')+bytes(23*61)
     graph_b=bytes([0,1,0,1,2,6])+b'Hello!'.ljust(57,b'\0')+bytes(23*61)
     ida=hashlib.sha256(b'EWGMAP09'+graph_a+guide_a+cells).hexdigest()
     idb=hashlib.sha256(b'EWGMAP09'+graph_b+guide_b+cells).hexdigest()
     bridge=(ROOT/'src/platform/world_bridge.c').read_text()
     helpers='\n'.join(function(bridge,name) for name in ('Decimal','WorldBridge_GeneratedCaveReady','CaveLine','CavePump','IsGeneratedCaveMap','MapCoords'))
     global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\n#define OBJECT_EVENT_TEMPLATES_COUNT 64\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nstruct ObjectEventTemplate {u8 localId,graphicsId,kind;s16 x,y;u8 elevation,movementType;u16 trainerType,trainerRange_berryTreeId;const u8 *script;u16 flagId;};\nstruct MapEvents {u8 objectEventCount,warpCount,coordEventCount,bgEventCount;const struct ObjectEventTemplate *objectEvents;const void *warps,*coordEvents,*bgEvents;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;const struct MapEvents *events;} gMapHeader;\n'''
     code=r'''
#include <assert.h>
#include <limits.h>
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
static struct {bool8 connected,caveAvailable,staging,caveReturning,caveV2Probe,caveV3Probe,caveV4Probe,caveV5Probe,caveV6Probe,caveV7Probe,caveV8Probe,caveV9Probe,caveV9TProbe,caveV9GProbe,terrainPending,terrainReportPending,terrainReportedApplied;u32 terrainRevision;u8 terrainSize,terrainData[193];u8 eventHead,eventCount;unsigned eventSetSeq;struct {u8 kind,state,rule[61],x,y,terrain,tiles[193],tilesSize;unsigned sequence;} eventQueue[8];enum CaveState caveState;unsigned caveTimeout,caveRetry,snapshotAge;char caveExpected[65];struct WorldCaveWire caveWire;size_t outputSize;char output[4096];} sWorld;
static int leaving,disconnected;static struct WarpData destination;static struct MapEvents events;
const u8 GeneratedWorld_Wilds_EventScript_Guide[]={0};const u8 GeneratedWorld_Wilds_EventScript_Cast2[]={0},GeneratedWorld_Wilds_EventScript_Cast3[]={0},GeneratedWorld_Wilds_EventScript_Graph[]={0};u16 gSpecialVar_LastTalked;extern u8 gGeneratedWildsGuideText[58],gGeneratedEventText[58];
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
static int tileX,tileY,tileValue,draws;void MapGridSetMetatileEntryAt(int x,int y,u16 value){tileX=x;tileY=y;tileValue=value;}void CurrentMapDrawMetatileAt(int x,int y){(void)x;(void)y;draws++;}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){leaving++;}
static int ready=1;static bool8 Ready(void){return ready;}
static int WorldCatalog_Coords(unsigned g,unsigned n,unsigned x,unsigned y){(void)g;(void)n;(void)x;(void)y;return 0;}
static char lastOutput[4096];static void Flush(void){memcpy(lastOutput,sWorld.output,sWorld.outputSize);lastOutput[sWorld.outputSize]=0;sWorld.outputSize=0;}
static void Disconnect(void){disconnected=1;sWorld.connected=0;}
''' + helpers + r'''
static const char *snapshotRev="1",*snapshotHex="020303020a0a00";
static int deliver(const char *id,char *guide,const char *graph){
 char *begin[]={"CAVE","BEGIN",(char *)id,"EVENTS"};char *meta[]={"CAVE","CAST",(char *)id,guide};char *end[]={"CAVE","END",(char *)id};
 char row[64],idx[4];char *parts[]={"CAVE","ROW",(char *)id,idx,row};
 assert(CaveLine(4,begin));assert(CaveLine(4,meta));
 for(int c=0;c<6;c++){char chunk[513],num[2]={(char)('0'+c),0};int len=c<5?512:372;
  memcpy(chunk,graph+c*512,len);chunk[len]=0;char *part[]={"CAVE","EVENTS",(char*)id,num,chunk};assert(CaveLine(5,part));}
 char *terrain[]={"CAVE","TERRAIN",(char*)id,(char*)snapshotRev,(char*)snapshotHex};assert(CaveLine(5,terrain));
 for(int y=0;y<63;y++){
  for(int x=0;x<63;x++)row[x]=(x==0||y==0||x==62||y==62||(x==10&&y==10))?'#':'.';
  row[63]=0;snprintf(idx,sizeof(idx),"%d",y);assert(CaveLine(5,parts));
 }
 return CaveLine(3,end);
}
int main(void){const char *a="ID_A",*b="ID_B";struct MapLayout base={19,26,0,0,0,0};(void)b;
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;gMapHeader.events=&events;save.location=(struct WarpData){3,4,0,8,9};
 sWorld.connected=1;sWorld.caveAvailable=1;sWorld.caveV2Probe=1;sWorld.caveV3Probe=1;sWorld.caveV4Probe=1;sWorld.caveV5Probe=1;sWorld.caveV6Probe=1;sWorld.caveV7Probe=1;sWorld.caveV8Probe=1;sWorld.caveV9Probe=1;sWorld.caveV9TProbe=1;sWorld.caveV9GProbe=1;sWorld.caveState=CAVE_WAIT;
 sWorld.caveV9GProbe=0;assert(!deliver(a,"META_A_SENTINEL","GRAPH_A_SENTINEL"));WorldCaveWire_Reset(&sWorld.caveWire);sWorld.caveState=CAVE_WAIT;sWorld.caveV9GProbe=1;assert(deliver(a,"META_A_SENTINEL","GRAPH_A_SENTINEL"));assert(sWorld.caveState==CAVE_ACK);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);
 char *ok[]={"CAVE","OK",(char*)a};assert(CaveLine(3,ok));CavePump();assert(strstr(lastOutput," 1 STAGED"));
 assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(save.location.mapNum==1);assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x0487 && GeneratedMap_ResolveLayout(&base)->map[10*63+10]==0x3001 && sWorld.terrainRevision==1);assert(gMapHeader.events->objectEventCount==2 && gMapHeader.events->objectEvents[0].graphicsId==7);assert(gGeneratedWildsGuideText[0]==0xd1);assert(!GeneratedMap_SharedCoordValid(2,1));assert(!GeneratedMap_SharedCoordValid(20,20));assert(GeneratedMap_SharedCoordValid(40,40));assert(MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_WILDS),MAP_NUM(MAP_GENERATED_WORLD_WILDS),61,61));assert(!MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_CAVE),MAP_NUM(MAP_GENERATED_WORLD_CAVE),61,61));assert(GeneratedMap_SharedCoordValid(61,61));assert(!GeneratedMap_SharedCoordValid(63,61));assert(GeneratedMap_MatchesPreparedEventWilds(sWorld.caveWire.events,WORLD_CAVE_EVENT_BYTES,sWorld.caveWire.cast,WORLD_CAVE_CAST_BYTES,sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));assert(!GeneratedMap_MatchesPreparedWilds(sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));assert(!GeneratedMap_MatchesPreparedLarge(sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));
 assert(!GeneratedMap_SharedCoordValid(3,3) && GeneratedMap_SharedCoordValid(10,10));assert(MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_WILDS),MAP_NUM(MAP_GENERATED_WORLD_WILDS),10,10));
 u8 disconnected[]={1,1,2,2};assert(!GeneratedMap_ValidateSharedTerrain(disconnected,sizeof(disconnected)));
 u8 isolated[]={4,19,20,2,20,19,2,20,21,2,21,20,2};assert(!GeneratedMap_ValidateSharedTerrain(isolated,sizeof(isolated)));
 char *terrain2[]={"CAVE","TERRAIN",(char*)a,"2","020303020a0a01"};assert(CaveLine(5,terrain2));CavePump();assert(!sWorld.terrainPending && sWorld.terrainRevision==2 && draws==1);assert(GeneratedMap_ResolveLayout(&base)->map[10*63+10]==0x300d);
 u8 dangerous[]={2,3,3,0,10,10,1};assert(GeneratedMap_ValidateSharedTerrain(dangerous,sizeof(dangerous)));assert(!GeneratedMap_ApplySharedTerrain(dangerous,sizeof(dangerous)));assert(!GeneratedMap_SharedCoordValid(3,3));
 assert(GeneratedMap_Leave());save.location=destination;GeneratedMap_ResolveLayout(&base);
 u8 reset[]={0};assert(GeneratedMap_StageSharedTerrain(reset,sizeof(reset)));assert(GeneratedMap_SharedCoordValid(3,3) && !GeneratedMap_SharedCoordValid(10,10));
 assert(GeneratedMap_Enter());save.location=destination;assert(GeneratedMap_ResolveLayout(&base)->map[10*63+10]==0x0487);
 return 0;}
'''.replace('ID_A',ida).replace('ID_B',idb).replace('META_A_SENTINEL',guide_a.hex()).replace('META_B_SENTINEL',guide_b.hex()).replace('GRAPH_A_SENTINEL',graph_a.hex()).replace('GRAPH_B_SENTINEL',graph_b.hex())
     with tempfile.TemporaryDirectory() as temp:
         p=Path(temp);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
         for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
             (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void SetWarpDestination(s8,s8,s8,s8,s8);void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void PlayerGetDestCoords(s16*,s16*);void StoreInitialPlayerAvatarState(void);void DoWarp(void);\n#define MAP_OFFSET 7\n')
         (p/'field_camera.h').write_text('#include "global.h"\nvoid CurrentMapDrawMetatileAt(int,int);void MapGridSetMetatileEntryAt(int,int,u16);\n')
         (p/'event_data.h').write_text('#include "global.h"\nextern u16 gSpecialVar_LastTalked;\n')
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
         cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-DGENERATED_WILDS_EVENTS=1','-DGENERATED_WILDS_SHARED_TERRAIN=1','-DGENERATED_WILDS_SHARED_GEOMETRY=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
         build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
         result=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)







 def test_native_negotiates_geometry_then_terrain(self):
     src=(ROOT/'src/platform/world_bridge.c').read_text()
     code=r'''#include <assert.h>
#include <limits.h>
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
#define GENERATED_WILDS_EVENTS 1
#define GENERATED_WILDS_SHARED_TERRAIN 1
#define GENERATED_WILDS_SHARED_GEOMETRY 1
static struct {bool8 rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,caveProbe,caveLegacy,caveV2Probe,caveV2Legacy,caveV3Probe,caveV3Legacy,caveV4Probe,caveV4Legacy,caveV5Probe,caveV5Legacy,caveV6Probe,caveV6Legacy,caveV7Probe,caveV7Legacy,caveV8Probe,caveV8Legacy,caveV9Probe,caveV9Legacy,caveV9TProbe,caveV9TLegacy,caveV9GProbe,caveV9GLegacy;char trainer[25],token[65],output[4096];int outputSize;} sWorld;
''' + function(src,'CaveProbeRejected') + function(src,'QueueHello') + r'''
int main(void){char *err[]={"ERROR","AUTH"};strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");
QueueHello(0);assert(strstr(sWorld.output,"CAVE9G\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV9GLegacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE9T\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV9TLegacy);
QueueHello(0);assert(strstr(sWorld.output,"CAVE9\n"));assert(CaveProbeRejected(2,err)&&sWorld.caveV9Legacy);
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



 def test_native_wire_accepts_positive_empty_geometry_revision(self):
  code=r'''#include <assert.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){struct WorldCaveWire w={0};char id[65];memset(id,'a',64);id[64]=0;
w.active=1;w.version=9;w.castSeen=1;w.nextEventChunk=6;memcpy(w.id,id,65);
const char *ok[]={"CAVE","TERRAIN",id,"3","00"};assert(WorldCaveWire_Feed(&w,5,ok)==0 && w.terrainSeen && w.terrainRevision==3 && w.terrain[0]==0);
WorldCaveWire_Reset(&w);w.active=1;w.version=9;w.castSeen=1;w.nextEventChunk=6;memcpy(w.id,id,65);
const char *bad[]={"CAVE","TERRAIN",id,"0","01010200"};assert(WorldCaveWire_Feed(&w,5,bad)<0);return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-DGENERATED_WILDS_EVENTS=1','-DGENERATED_WILDS_SHARED_TERRAIN=1','-DGENERATED_WILDS_SHARED_GEOMETRY=1','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr);run=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
