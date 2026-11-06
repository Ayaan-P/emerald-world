"""Durable terrain control and negotiation using in-memory authority only."""
import hashlib,json,subprocess,tempfile,threading,unittest
from test_save_isolation import function
from pathlib import Path
from unittest.mock import patch
from test_large_generated_cave import DOC
from test_shared_generated_cave import MemoryAuthority
from world import wilds_events,shared_terrain_control
from world.shared_cave import SharedCave
ROOT=Path(__file__).resolve().parents[2]

class SharedTerrainWorld(unittest.TestCase):
 def blob(self):
  return wilds_events.compile_document({'blueprint':DOC,'cast':[{'gfx':7,'text':'Hi!'}], 'events':{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Hi!'}]}})
 def test_owner_persistence_legacy_and_offer_races(self):
  blob=self.blob();area=SharedCave(blob);identity=area.identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    with self.assertRaises(ValueError):server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}])
    server._replace_cave(blob)
    def connect(name,suffix):
     ident=server.create_identity(name);c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
     server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLY%s'%(name,ident['token'],suffix)).encode());self.assertIn(b'WELCOME 1',c['out']);c['out'].clear();return c
    def get(c):server._line(c,b'CAVE GET');out=bytes(c['out']);c['out'].clear();return out
    def ack(c):server._line(c,('CAVE ACK '+identity).encode());out=bytes(c['out']);c['out'].clear();return out
    t1=connect('Alice','CAVE9T');legacy=connect('Bob','CAVE9');pending=connect('Carol','CAVE9T')
    self.assertIn(f'CAVE TERRAIN {identity} 0 00\n'.encode(),get(t1));self.assertIn(b'CAVE OK',ack(t1))
    self.assertNotIn(b'CAVE TERRAIN',get(legacy));self.assertIn(b'CAVE OK',ack(legacy))
    self.assertIn(b'CAVE TERRAIN',get(pending))
    legacy['in_generated_cave']=True
    with self.assertRaises(ValueError):server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}])
    legacy['in_generated_cave']=False
    def admin_request(_socket,request,**kwargs):
     c={'id':None,'out':bytearray(),'closing':False,'sock':object()};server._admin_line(c,json.dumps(request).encode());return json.loads(c['out'])
    with patch('world.shared_terrain_control.admin_request',side_effect=admin_request):
     result=shared_terrain_control.publish(p/'owner',identity,[{'x':1,'y':2,'terrain':'grass'},{'x':2,'y':2,'terrain':'tall_grass'}])
    self.assertTrue(result['ok']);self.assertEqual(result['revision'],1);self.assertEqual(result['queued'],1)
    self.assertIn(f'CAVE TERRAIN {identity} 1 02010200020201\n'.encode(),t1['out']);self.assertIn(b'CAVE RESET',legacy['out'])
    t1['out'].clear();same=server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}]);self.assertFalse(same['changed']);self.assertEqual(same['revision'],1);self.assertFalse(t1['out'])
    self.assertIn(b'CAVE RESET',ack(pending)) # old offered snapshot cannot be acknowledged after an update
    for bad in ([{'x':1,'y':1,'terrain':'grass'}],[{'x':1,'y':2,'terrain':'grass'}]*2):
     with self.assertRaises(ValueError):server.set_shared_terrain(identity,bad)
    self.assertEqual(server._active_terrain()[0],1)
   finally:server.close()
   restored=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True)
   try:
    self.assertEqual(restored._active_terrain(),(1,bytes.fromhex('02010200020201')))
    ident=restored.create_identity('Dave');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    restored._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9'%(ident['id'],ident['token'])).encode());c['out'].clear();restored._line(c,b'CAVE GET');self.assertEqual(c['out'],b'CAVE NONE\n')
   finally:restored.close()
 def test_two_compatible_trainers_receive_same_durable_revision(self):
  blob=self.blob();identity=SharedCave(blob).identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);players=[]
    for name,xy in (('Alice',(1,1)),('Bob',(1,2))):
     ident=server.create_identity(name);c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
     server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(ident['id'],ident['token'])).encode());c['out'].clear()
     server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
     g,n=server.wilds_map;server._line(c,(f'STATE 1 {g} {n} {xy[0]} {xy[1]} 1 7 1 '+('a'*16)+' '+('b'*16)).encode());c['out'].clear();players.append(c)
    result=server.set_shared_terrain(identity,[{'x':2,'y':2,'terrain':'tall_grass'}])
    self.assertEqual(result['queued'],2);expected=f'CAVE TERRAIN {identity} 1 01020201\n'.encode()
    self.assertEqual(bytes(players[0]['out']),expected);self.assertEqual(bytes(players[1]['out']),expected)
   finally:server.close()
 def test_shared_overlay_capacity_is_atomic(self):
  blob=self.blob();area=SharedCave(blob);identity=area.identity
  coords=[(x,y) for x in range(63) for y in range(63) if area.walkable(x,y) and (x,y) not in ((1,1),(61,60),(61,61))]
  self.assertGreaterEqual(len(coords),65)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);patch=[{'x':x,'y':y,'terrain':'grass'} for x,y in coords[:64]]
    self.assertEqual(server.set_shared_terrain(identity,patch)['tiles'],64);before=server._active_terrain()
    x,y=coords[64]
    with self.assertRaises(ValueError):server.set_shared_terrain(identity,[{'x':x,'y':y,'terrain':'grass'}])
    self.assertEqual(server._active_terrain(),before)
   finally:server.close()
 def test_agent_inspects_geometry_and_client_reported_delivery(self):
  blob=self.blob();identity=SharedCave(blob).identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);ident=server.create_identity('Alice');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(ident['id'],ident['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
    def owner(_socket,request,**kwargs):
     admin={'id':None,'out':bytearray(),'closing':False,'sock':object()};server._admin_line(admin,json.dumps(request).encode());return json.loads(admin['out'])
    with patch('world.shared_terrain_control.admin_request',side_effect=owner):
     first=shared_terrain_control.inspect(p/'owner',identity);self.assertEqual(first['revision'],0);self.assertEqual(len(first['rows']),63);self.assertEqual(first['characters'],[{'npc':1,'x':2,'y':1}]);self.assertEqual(first['players'][0]['reported_phase'],'pending')
     with patch('builtins.print') as output:
      self.assertEqual(shared_terrain_control.main(['--admin-socket',str(p/'owner'),'--area',identity,'--inspect']),0)
      self.assertEqual(json.loads(output.call_args.args[0])['revision'],0)

     server._line(c,f'CAVE TERRAINACK {identity} 0 STAGED'.encode());self.assertEqual(shared_terrain_control.inspect(p/'owner',identity)['players'][0]['reported_phase'],'staged')
     server._line(c,f'CAVE TERRAINACK {identity} 0 APPLIED'.encode());server._line(c,f'CAVE TERRAINACK {identity} 0 STAGED'.encode());self.assertEqual(shared_terrain_control.inspect(p/'owner',identity)['players'][0]['reported_phase'],'applied')
     server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}]);second=shared_terrain_control.inspect(p/'owner',identity)
     self.assertEqual(second['revision'],1);self.assertEqual(second['players'][0]['reported_phase'],'pending');self.assertEqual(second['tiles'],[{'x':1,'y':2,'terrain':'grass'}])
     server._line(c,f'CAVE TERRAINACK {identity} 1 APPLIED'.encode());self.assertEqual(shared_terrain_control.inspect(p/'owner',identity)['players'][0]['reported_phase'],'applied')
     c['cave_next']=0;server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());self.assertEqual(shared_terrain_control.inspect(p/'owner',identity)['players'][0]['reported_phase'],'pending')
   finally:server.close()
 def test_inflight_offer_and_corrupt_storage_fail_closed(self):
  blob=self.blob();identity=SharedCave(blob).identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);ident=server.create_identity('Alice');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(ident['id'],ident['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
    c['cave_next']=0;server._line(c,b'CAVE GET');self.assertIn(b'CAVE TERRAIN',c['out']);c['out'].clear()
    result=server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}]);self.assertEqual(result['queued'],0);self.assertFalse(c['out'])
    server._line(c,('CAVE ACK '+identity).encode());self.assertIn(b'CAVE RESET',c['out']);c['out'].clear()
    c['cave_next']=0;server._line(c,b'CAVE GET');self.assertIn(f'CAVE TERRAIN {identity} 1 01010200'.encode(),c['out'])
    with server.db:server.db.execute('UPDATE generated_area_terrain SET payload=? WHERE identity=?',(b'\xff',identity))
    with self.assertRaises(ValueError):server._active_terrain()
   finally:server.close()
 def test_persistence_and_backpressure_are_atomic(self):
  blob=self.blob();identity=SharedCave(blob).identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);ident=server.create_identity('Alice');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(ident['id'],ident['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out']=bytearray(b'x'*65530)
    with self.assertRaises(ValueError):server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}])
    self.assertEqual(server._active_terrain(),(0,b'\0'));c['out'].clear()
    server.db.execute('PRAGMA query_only=ON')
    with self.assertRaises(ValueError):server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}])
    server.db.execute('PRAGMA query_only=OFF');self.assertEqual(server._active_terrain(),(0,b'\0'));self.assertFalse(c['out'])
   finally:server.close()
 def test_postcommit_delivery_failure_is_reported_not_rolled_back(self):
  blob=self.blob();identity=SharedCave(blob).identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
   try:
    server._replace_cave(blob);ident=server.create_identity('Alice');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T'%(ident['id'],ident['token'])).encode());c['out'].clear()
    server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
    with patch.object(server,'_queue',side_effect=OSError('closed')):
     result=server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}])
    self.assertTrue(result['ok']);self.assertEqual(result['delivery_failed'],1);self.assertEqual(result['queued'],0);self.assertTrue(c['closing']);self.assertEqual(server._active_terrain()[0],1)
   finally:server.close()
 def test_legacy_entry_race_never_admits_stale_terrain(self):
  blob=self.blob();identity=SharedCave(blob).identity
  for _ in range(8):
   with tempfile.TemporaryDirectory() as t:
    p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob)
    try:
     server._replace_cave(blob);ident=server.create_identity('Old');c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
     server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9'%(ident['id'],ident['token'])).encode());c['out'].clear()
     server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
     g,n=server.wilds_map;barrier=threading.Barrier(2);result=[]
     def edit():
      barrier.wait()
      try:server.set_shared_terrain(identity,[{'x':1,'y':2,'terrain':'grass'}]);result.append('painted')
      except ValueError:result.append('blocked')
     def enter():
      barrier.wait();server._line(c,(f'STATE 1 {g} {n} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode())
     a=threading.Thread(target=edit);b=threading.Thread(target=enter);a.start();b.start();a.join();b.join()
     if result==['painted']:self.assertFalse(c.get('in_generated_cave',False));self.assertIsNone(c.get('cave_ack'))
     else:self.assertEqual(result,['blocked']);self.assertTrue(c.get('in_generated_cave'));self.assertEqual(server._active_terrain()[0],0)
    finally:server.close()
 def test_native_wire_accepts_ordered_snapshot_and_rejects_bad_metadata(self):
  import subprocess
  code=r'''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[1024];struct WorldCaveWire w={0};int r=0;
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\n")]=0;
for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;
r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}
return r==1 && w.version==9 && w.terrainSeen && ((w.terrainRevision==1 && w.terrainSize==4 && w.terrain[0]==1) || (w.terrainRevision==0 && w.terrainSize==1 && w.terrain[0]==0)) ? 0:3;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   root=Path(__file__).resolve().parents[2]
   cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-DGENERATED_WILDS_EVENTS=1','-DGENERATED_WILDS_SHARED_TERRAIN=1','-iquote',str(p),'-iquote',str(root/'include'),str(root/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
   area=SharedCave(self.blob());terrain=bytes.fromhex('01010200');frames=area.frames((1,terrain));run=lambda x:subprocess.run([str(p/'test')],input=x,capture_output=True,text=True).returncode
   self.assertEqual(run(frames),0);self.assertEqual(run(area.frames((0,b'\0'))),0);self.assertNotEqual(run(area.frames((2,b'\0'))),0);line=f'CAVE TERRAIN {area.identity} 1 {terrain.hex()}\n'
   for bad in (frames.replace(line,line+line),frames.replace(line,line.replace(' 1 ',' 0 ')),frames.replace(line,line[:-3]+'zz\n')):
    self.assertNotEqual(run(bad),0)

 def test_native_shared_terrain_snapshot_and_updates(self):
     groups=json.loads((ROOT/'data/maps/map_groups.json').read_text())
     group=groups['group_order'].index('gMapGroup_GeneratedWorld')
     rows=['#'*63]+['#'+'.'*61+'#']*61+['#'*63]
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
static struct {bool8 connected,caveAvailable,staging,caveReturning,caveV2Probe,caveV3Probe,caveV4Probe,caveV5Probe,caveV6Probe,caveV7Probe,caveV8Probe,caveV9Probe,caveV9TProbe,terrainPending,terrainReportPending,terrainReportedApplied;u32 terrainRevision;u8 terrainSize,terrainData[193];u8 eventHead,eventCount;unsigned eventSetSeq;struct {u8 kind,state,rule[61],x,y,terrain,tiles[193],tilesSize;unsigned sequence;} eventQueue[8];enum CaveState caveState;unsigned caveTimeout,caveRetry,snapshotAge;char caveExpected[65];struct WorldCaveWire caveWire;size_t outputSize;char output[4096];} sWorld;
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
static const char *snapshotRev="1",*snapshotHex="01030301";
static void deliver(const char *id,char *guide,const char *graph){
 char *begin[]={"CAVE","BEGIN",(char *)id,"EVENTS"};char *meta[]={"CAVE","CAST",(char *)id,guide};char *end[]={"CAVE","END",(char *)id};
 char row[64],idx[4];char *parts[]={"CAVE","ROW",(char *)id,idx,row};
 assert(CaveLine(4,begin));assert(CaveLine(4,meta));
 for(int c=0;c<6;c++){char chunk[513],num[2]={(char)('0'+c),0};int len=c<5?512:372;
  memcpy(chunk,graph+c*512,len);chunk[len]=0;char *part[]={"CAVE","EVENTS",(char*)id,num,chunk};assert(CaveLine(5,part));}
 char *terrain[]={"CAVE","TERRAIN",(char*)id,(char*)snapshotRev,(char*)snapshotHex};assert(CaveLine(5,terrain));
 for(int y=0;y<63;y++){
  for(int x=0;x<63;x++)row[x]=(x==0||y==0||x==62||y==62)?'#':'.';
  row[63]=0;snprintf(idx,sizeof(idx),"%d",y);assert(CaveLine(5,parts));
 }
 assert(CaveLine(3,end));
}
int main(void){const char *a="ID_A",*b="ID_B";struct MapLayout base={19,26,0,0,0,0};
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;gMapHeader.events=&events;save.location=(struct WarpData){3,4,0,8,9};
 sWorld.connected=1;sWorld.caveAvailable=1;sWorld.caveV2Probe=1;sWorld.caveV3Probe=1;sWorld.caveV4Probe=1;sWorld.caveV5Probe=1;sWorld.caveV6Probe=1;sWorld.caveV7Probe=1;sWorld.caveV8Probe=1;sWorld.caveV9Probe=1;sWorld.caveV9TProbe=1;sWorld.caveState=CAVE_WAIT;
 deliver(a,"META_A_SENTINEL","GRAPH_A_SENTINEL");assert(sWorld.caveState==CAVE_ACK);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);
 char *ok[]={"CAVE","OK",(char*)a};assert(CaveLine(3,ok));CavePump();assert(strstr(lastOutput," 1 STAGED"));
 assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(save.location.mapNum==1);assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x300d && sWorld.terrainRevision==1);assert(gMapHeader.events->objectEventCount==2 && gMapHeader.events->objectEvents[0].graphicsId==7);assert(gGeneratedWildsGuideText[0]==0xd1);assert(!GeneratedMap_SharedCoordValid(2,1));assert(!GeneratedMap_SharedCoordValid(20,20));assert(GeneratedMap_SharedCoordValid(40,40));assert(MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_WILDS),MAP_NUM(MAP_GENERATED_WORLD_WILDS),61,61));assert(!MapCoords(MAP_GROUP(MAP_GENERATED_WORLD_CAVE),MAP_NUM(MAP_GENERATED_WORLD_CAVE),61,61));assert(GeneratedMap_SharedCoordValid(61,61));assert(!GeneratedMap_SharedCoordValid(63,61));assert(GeneratedMap_MatchesPreparedEventWilds(sWorld.caveWire.events,WORLD_CAVE_EVENT_BYTES,sWorld.caveWire.cast,WORLD_CAVE_CAST_BYTES,sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));assert(!GeneratedMap_MatchesPreparedWilds(sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));assert(!GeneratedMap_MatchesPreparedLarge(sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));
 char *terrain2[]={"CAVE","TERRAIN",(char*)a,"2","02030300040401"};assert(CaveLine(5,terrain2));assert(sWorld.terrainPending);ready=0;CavePump();assert(sWorld.terrainPending && draws==0);ready=1;CavePump();assert(!sWorld.terrainPending && sWorld.terrainRevision==2 && draws==2 && strstr(lastOutput," 2 APPLIED"));assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x3001);snapshotRev="2";snapshotHex="02030300040401";
 char *stale[]={"CAVE","TERRAIN",(char*)a,"1","01030301"};assert(CaveLine(5,stale) && !sWorld.terrainPending && sWorld.terrainRevision==2);
 char *badTerrain[]={"CAVE","TERRAIN",(char*)a,"3","01010100"};assert(!CaveLine(5,badTerrain) && sWorld.terrainRevision==2);
 assert(GeneratedMap_EventState()==0);assert(!GeneratedMap_SetSharedEventState(16));gSpecialVar_LastTalked=1;GeneratedMap_RunEvent();assert(GeneratedMap_EventState()==1);
 /* Reconnect to the same identity without evicting a player already inside. */
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(a,"META_A_SENTINEL","GRAPH_A_SENTINEL");
 assert(sWorld.caveState==CAVE_ACK);assert(GeneratedMap_EventState()==1);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);assert(CaveLine(3,ok));
 char *set[]={"CAVE","EVENTSET",(char*)a,"1","5"};assert(CaveLine(5,set));assert(sWorld.eventCount==1);ready=0;CavePump();assert(GeneratedMap_EventState()==1 && sWorld.eventCount==1);ready=1;CavePump();assert(GeneratedMap_EventState()==5);assert(strstr(lastOutput," 1 APPLIED"));assert(CaveLine(5,set));assert(!sWorld.eventCount);
 char *other[]={"CAVE","EVENTSET","ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff","2","6"};assert(CaveLine(5,other));assert(!sWorld.eventCount);
 u8 badRule[61]={5,1,6,1,1};assert(!GeneratedMap_SetSharedEventRule(badRule,sizeof(badRule)));
 char *patch[]={"CAVE","EVENTRULE",(char*)a,"3","5","1","6","4869"};assert(CaveLine(8,patch));assert(sWorld.eventCount==1);CavePump();assert(!sWorld.eventCount);assert(strstr(lastOutput," 3 APPLIED"));
 assert(GeneratedMap_MatchesPreparedEventWilds(sWorld.caveWire.events,WORLD_CAVE_EVENT_BYTES,sWorld.caveWire.cast,WORLD_CAVE_CAST_BYTES,sWorld.caveWire.cells,WORLD_CAVE_LARGE_CELLS));
 gSpecialVar_LastTalked=1;GeneratedMap_RunEvent();assert(GeneratedMap_EventState()==6 && gGeneratedEventText[0]==0xc2 && gGeneratedEventText[1]==0xdd);
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(a,"META_A_SENTINEL","GRAPH_A_SENTINEL");assert(sWorld.caveState==CAVE_ACK);CavePump();assert(CaveLine(3,ok));
 assert(GeneratedMap_SetSharedEventState(5));GeneratedMap_RunEvent();assert(GeneratedMap_EventState()==6);
 char *set2[]={"CAVE","EVENTSET",(char*)a,"4","7"};char *patch2[]={"CAVE","EVENTRULE",(char*)a,"5","7","1","8","4869"};
 ready=0;assert(CaveLine(5,set2));assert(CaveLine(8,patch2));CavePump();assert(sWorld.eventCount==2 && GeneratedMap_EventState()==6);
 ready=1;CavePump();assert(sWorld.eventCount==1 && GeneratedMap_EventState()==7);CavePump();assert(sWorld.eventCount==0);GeneratedMap_RunEvent();assert(GeneratedMap_EventState()==8);
 char *invalid[]={"CAVE","EVENTRULE",(char*)a,"6","8","1","9","01"};assert(CaveLine(8,invalid));CavePump();assert(strstr(lastOutput," 6 REJECTED") && GeneratedMap_EventState()==8);
 char *tile[]={"CAVE","EVENTTILE",(char*)a,"7","3","3","1"};assert(CaveLine(7,tile));CavePump();assert(strstr(lastOutput," 7 APPLIED") && tileX==10 && tileY==10 && tileValue==0x300d && draws==7);assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x300d);
 char *blocked[]={"CAVE","EVENTTILE",(char*)a,"8","2","1","0"};assert(CaveLine(7,blocked));CavePump();assert(strstr(lastOutput," 8 REJECTED") && draws==7);
 char *tiles[]={"CAVE","EVENTTILES",(char*)a,"9","02030300040401"};assert(CaveLine(5,tiles));CavePump();assert(strstr(lastOutput," 9 APPLIED") && draws==9);assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x3001 && GeneratedMap_ResolveLayout(&base)->map[4*63+4]==0x300d);
 char *duplicate[]={"CAVE","EVENTTILES",(char*)a,"10","02030300030301"};assert(CaveLine(5,duplicate));CavePump();assert(strstr(lastOutput," 10 REJECTED") && draws==9);assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x3001);
 u8 many[193];many[0]=64;for(int i=0;i<64;i++){many[1+3*i]=3+i%8;many[2+3*i]=3+i/8;many[3+3*i]=i%2;}
 assert(GeneratedMap_SetSharedEventTiles(many,sizeof(many)) && draws==73);many[1+3*63]=1;many[2+3*63]=1;assert(!GeneratedMap_SetSharedEventTiles(many,sizeof(many)) && draws==73);



 /* The same terrain and characters with a different event graph is a different identity. It must
 leave the old cave before staging or acknowledging the replacement. */
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(b,"META_B_SENTINEL","GRAPH_B_SENTINEL");
 assert(sWorld.caveState==CAVE_MISMATCH && gGeneratedWildsGuideText[0]==0xd1);
 CavePump();assert(sWorld.caveReturning && leaving==2);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_WAIT_OK);char *ok2[]={"CAVE","OK",(char*)b};assert(CaveLine(3,ok2));
 assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(gMapHeader.events->objectEvents[0].graphicsId==7 && gGeneratedWildsGuideText[0]==0xd1 && !disconnected);assert(GeneratedMap_ResolveLayout(&base)->map[3*63+3]==0x3001 && GeneratedMap_ResolveLayout(&base)->map[4*63+4]==0x300d);assert(GeneratedMap_EventState()==0);gSpecialVar_LastTalked=1;GeneratedMap_RunEvent();assert(GeneratedMap_EventState()==2);
 /* An unsupported profile response must not be accepted without v2 negotiation. */
 sWorld.caveState=CAVE_WAIT;sWorld.caveV2Probe=0;WorldCaveWire_Reset(&sWorld.caveWire);
 char *bad[]={"CAVE","BEGIN",(char*)a,"1"};assert(!CaveLine(4,bad));
 sWorld.caveV2Probe=1;sWorld.caveV6Probe=0;WorldCaveWire_Reset(&sWorld.caveWire);
 char *unadvertised[]={"CAVE","BEGIN",(char*)a,"WILDS"};assert(!CaveLine(4,unadvertised));
 /* Legacy clients receiving NONE after an in-flight reset return safely. */
 sWorld.caveState=CAVE_WAIT_RESET;char *none[]={"CAVE","NONE"};
 assert(CaveLine(2,none)&&sWorld.caveState==CAVE_RETURN_NONE);
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
         cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-DGENERATED_WILDS_EVENTS=1','-DGENERATED_WILDS_SHARED_TERRAIN=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
         build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
         result=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)






 def test_native_negotiates_terrain_then_v9(self):
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
static struct {bool8 rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,caveProbe,caveLegacy,caveV2Probe,caveV2Legacy,caveV3Probe,caveV3Legacy,caveV4Probe,caveV4Legacy,caveV5Probe,caveV5Legacy,caveV6Probe,caveV6Legacy,caveV7Probe,caveV7Legacy,caveV8Probe,caveV8Legacy,caveV9Probe,caveV9Legacy,caveV9TProbe,caveV9TLegacy;char trainer[25],token[65],output[4096];int outputSize;} sWorld;
''' + function(src,'CaveProbeRejected') + function(src,'QueueHello') + r'''
int main(void){char *err[]={"ERROR","AUTH"};strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");
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



