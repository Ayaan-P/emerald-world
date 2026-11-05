"""Exercise authenticated relevance-window negotiation without sockets."""
from pathlib import Path
import ast,subprocess,tempfile,unittest
from test_save_isolation import function
from world.server import WorldServer

ROOT=Path(__file__).resolve().parents[2]
class MemoryServer(WorldServer):
 def _queue(self,c,text):c['out'].extend(text.encode())
 def _broadcast(self):pass

class ExtendedPeerWindow(unittest.TestCase):
 def test_legacy_and_opt_in_view_and_auth_boundary(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);server=MemoryServer(root/'s',root/'w',max_players=64);self.addCleanup(server.close)
   def connect(name,role):
    identity=server.create_identity(name)
    conn={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(conn,('HELLO 1 '+name+' '+identity['token']+(' '+role if role else '')).encode())
    return conn
   legacy=connect('legacy','SOCIALTRAVELCHAT');intermediate=connect('intermediate','SOCIALTRAVELCHATPEER16');extended=connect('extended','SOCIALTRAVELCHATPEER32')
   self.assertIn(b'WELCOME',legacy['out']);self.assertIn(b'WELCOME',intermediate['out']);self.assertIn(b'WELCOME',extended['out'])
   for i in range(40):
    server.peers[f'P{i:02}']={'id':f'P{i:02}','closing':False,'state':[1,1,i+1,3,1,7,1],'field':True}
   for conn,want in ((legacy,8),(intermediate,16),(extended,32)):
    conn['state']=[1,1,0,3,1,7,1]
    peers=[line for line in server._snapshot(conn).splitlines() if line.startswith('PEER ')]
    self.assertEqual(len(peers),want)
    self.assertTrue(any(line.startswith('PEER P00 ') for line in peers))
   for index,role in enumerate(('CONTROLPEER16','LINKPEER16','PEER16','BADPEER16','CONTROLPEER32','LINKPEER32','PEER32','BADPEER32')):
    rejected=connect('bad'+str(index),role)
    self.assertIn(b'ERROR AUTH',rejected['out']);self.assertIsNone(rejected['id'])
 def test_native_hello_capability_and_fallback(self):
  src=(ROOT/'src/platform/world_bridge.c').read_text()
  queue=function(src,'QueueHello')
  start=src.index('    if (!sWorld.connected) {',src.index('static bool8 Line(char *line)'))
  end=src.index('        if (n != 4 || strcmp(tokens[0], "WELCOME")',start)
  fallback=src[start:end]+'        return TRUE;\n    }\n    return TRUE;\n}'
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef int bool8;
#define TRUE 1
#define FALSE 0
#define WORLD_EXTENDED_OBJECTS 1
struct {int connected,rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,peer32Probe,peer32Legacy,peer16Probe,peer16Legacy;char output[256],trainer[25],token[65];int outputSize;} sWorld;
'''+queue+'\nstatic bool8 TestFallback(char **tokens, unsigned n)\n{\n'+fallback+r'''
int main(void){
 strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");QueueHello(0);
 assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYPEER32"));
 char *e[]={"ERROR","AUTH"};assert(!TestFallback(e,2));
 assert(sWorld.peer32Legacy && !sWorld.peer16Legacy && !sWorld.rallyLegacy);
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYPEER16"));
 assert(!TestFallback(e,2));assert(sWorld.peer16Legacy && !sWorld.rallyLegacy && !sWorld.travelLegacy && !sWorld.chatLegacy);
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLY\n"));assert(!strstr(sWorld.output,"PEER16"));
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)

 def test_native_parser_commits_thirtytwo_and_rejects_next(self):
  bridge=(ROOT/'src/platform/world_bridge.c').read_text()
  decl=bridge[bridge.index('#define WB_PEERS'):bridge.index('static bool8 Identifier')]
  code=r"""
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <limits.h>
#include "platform/world_rally.h"
#define FALSE 0
#define TRUE 1
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
static bool8 MapCoords(unsigned a,unsigned b,unsigned c,unsigned d){return a<2 && b<2 && c<64 && d<64;}
static bool8 WorldCatalog_Metatile(unsigned a,unsigned b,unsigned c){(void)a;(void)b;return c<1024;}
"""+decl+''.join(function(bridge,n) for n in ('Identifier','Decimal','ObjectText','Line'))+r"""
static int feed(const char *line){char b[200];strcpy(b,line);return Line(b);}
int main(void){
 strcpy(sWorld.trainer,"alice");sWorld.connected=1;
 assert(feed("BEGIN 1"));
 for(int i=0;i<32;i++){char b[100];snprintf(b,sizeof(b),"PEER P%02d 1 1 %d 2 1 7 1",i,i);assert(feed(b));}
 for(int i=0;i<8;i++){char b[100];snprintf(b,sizeof(b),"OBJECT O%02d 1 1 %d 30 7 48",i,i);assert(feed(b));}
 assert(feed("END"));assert(sWorld.live.peerCount==40 && sWorld.live.objectCount==8);
 assert(feed("BEGIN 2"));
 for(int i=0;i<32;i++){char b[100];snprintf(b,sizeof(b),"PEER P%02d 1 1 %d 2 1 7 1",i,i);assert(feed(b));}
 assert(!feed("PEER P32 1 1 32 2 1 7 1"));assert(sWorld.live.peerCount==40);
 return 0;
}
"""
  code='#include <assert.h>\n'+code
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror','-DPORTABLE','-DWORLD_EXTENDED_OBJECTS=1','-iquote',str(ROOT/'include'),str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)

 def test_real_reconciler_selects_sixteen_with_full_native_pool(self):
  src=(ROOT/'src/platform/world_bridge.c').read_text()
  code=r"""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned char u8; typedef int bool8;
#define TRUE 1
#define FALSE 0
#define WB_PEERS 16
#define WB_OBJECTS 8
#define WB_REMOTES 24
#define OBJECT_EVENTS_COUNT 32
#define MAX_SPRITES 96
#define WB_LOCALID 200
#define WB_MARKER 0x5742
#define MAP_OFFSET 7
struct Coord {int x,y;};
struct ObjectEvent {int active,isPlayer,localId,mapGroup,mapNum,spriteId;struct Coord currentCoords;};
struct Sprite {int inUse,data[8];};
struct Remote {char id[26];unsigned object,sprite,group,num;};
struct Peer {char id[26];unsigned group,num,x,y;};
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];struct Sprite gSprites[MAX_SPRITES];
struct {struct Remote remotes[WB_REMOTES];struct {unsigned peerCount;struct Peer peers[WB_REMOTES];}live; struct Peer field;unsigned group,num,visiblePeers;} sWorld;
static bool8 GridCoords(unsigned x,unsigned y){return x<64 && y<64;}
"""+''.join(function(src,n) for n in ('Owned','NativeNpcAt','SelectPeers'))+r"""
int main(void){
 unsigned order[WB_REMOTES];sWorld.group=sWorld.num=1;sWorld.visiblePeers=16;
 for(int i=0;i<16;i++){gObjectEvents[i].active=1;gObjectEvents[i].currentCoords.x=100+i;gObjectEvents[i].currentCoords.y=100;}
 sWorld.live.peerCount=16;
 for(int i=0;i<16;i++){struct Peer *p=&sWorld.live.peers[i];snprintf(p->id,sizeof(p->id),"P%d",i);p->group=p->num=1;p->x=i+1;p->y=2;}
 assert(SelectPeers(order)==16);for(int i=0;i<16;i++)assert(gObjectEvents[i].active);
 gObjectEvents[16].active=1;gObjectEvents[16].currentCoords.x=100;gObjectEvents[16].currentCoords.y=100;
 assert(SelectPeers(order)==15);return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)

 def test_actual_reconciler_keeps_sixteen_npcs_and_spawns_sixteen_peers(self):
  source=(ROOT/'src/platform/world_bridge.c').read_text()
  tree=ast.parse((ROOT/'test/world/test_presence_reconcile.py').read_text())
  literals=[node.value.value for node in ast.walk(tree) if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='fixture' for t in node.targets)
            and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)]
  self.assertEqual(len(literals),1)
  fixture=literals[0].replace('#define WB_PEERS 8','#define WB_PEERS 16').replace('#define OBJECT_EVENTS_COUNT 16','#define OBJECT_EVENTS_COUNT 32').replace('#define MAX_SPRITES 64','#define MAX_SPRITES 96').replace('#define WB_LOCALID 224','#define WB_LOCALID 200').replace('SpawnSpecialObjectEventParameterized','SpawnWorldObjectEventParameterized')
  fixture='#define WORLD_EXTENDED_OBJECTS 1\n'+fixture
  fixture+=''.join(function(source,n) for n in ('Owned','RemoveRemote','NativeNpcAt','SelectPeers','SyncEngine'))
  fixture+=r"""
#include <assert.h>
int main(void){
 sWorld.tilesLive=TRUE;sWorld.visiblePeers=16;
 for(int i=0;i<NUM_OBJ_EVENT_GFX;i++)graphics[i].paletteSlot=PALSLOT_NPC_1;
 for(int i=0;i<16;i++){gObjectEvents[i].active=TRUE;gObjectEvents[i].localId=i+1;gObjectEvents[i].currentCoords=(struct Coords){100+i,100};}
 sWorld.live.peerCount=16;
 for(int i=0;i<16;i++){struct Peer *p=&sWorld.live.peers[i];snprintf(p->id,sizeof(p->id),"P%d",i);p->x=i+1;p->y=2;p->facing=1;p->gfx=7;p->ready=1;}
 SyncEngine();assert(spawned==16);
 for(int i=0;i<16;i++){assert(gObjectEvents[i].active);assert(Owned(i));assert(sWorld.remotes[i].object>=16);}
 sWorld.live.peerCount=0;SyncEngine();assert(removed==16);
 for(int i=0;i<16;i++)assert(gObjectEvents[i].active);
 return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(fixture)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)

 def test_reconciler_spawns_thirtytwo_with_full_native_pool(self):
  source=(ROOT/'src/platform/world_bridge.c').read_text()
  tree=ast.parse((ROOT/'test/world/test_presence_reconcile.py').read_text())
  literals=[node.value.value for node in ast.walk(tree) if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='fixture' for t in node.targets)
            and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)]
  self.assertEqual(len(literals),1)
  fixture=literals[0].replace('#define WB_PEERS 8','#define WB_PEERS 32').replace('#define OBJECT_EVENTS_COUNT 16','#define OBJECT_EVENTS_COUNT 48').replace('#define MAX_SPRITES 64','#define MAX_SPRITES 96').replace('#define WB_LOCALID 224','#define WB_LOCALID 160').replace('SpawnSpecialObjectEventParameterized','SpawnWorldObjectEventParameterized')
  fixture='#define WORLD_EXTENDED_OBJECTS 1\n'+fixture
  fixture+=''.join(function(source,n) for n in ('Owned','RemoveRemote','NativeNpcAt','SelectPeers','SyncEngine'))
  fixture+=r"""
#include <assert.h>
int main(void){
 sWorld.tilesLive=TRUE;sWorld.visiblePeers=32;
 for(int i=0;i<NUM_OBJ_EVENT_GFX;i++)graphics[i].paletteSlot=PALSLOT_NPC_1;
 for(int i=0;i<16;i++){gObjectEvents[i].active=TRUE;gObjectEvents[i].localId=i+1;gObjectEvents[i].currentCoords=(struct Coords){100+i,100};}
 sWorld.live.peerCount=32;
 for(int i=0;i<32;i++){struct Peer *p=&sWorld.live.peers[i];snprintf(p->id,sizeof(p->id),"P%d",i);p->x=i%16+1;p->y=2+i/16;p->facing=1;p->gfx=7;p->ready=1;}
 SyncEngine();assert(spawned==32);
 for(int i=0;i<16;i++)assert(gObjectEvents[i].active);
 for(int i=0;i<32;i++){assert(Owned(i));assert(sWorld.remotes[i].object>=16);}
 sWorld.live.peerCount=0;SyncEngine();assert(removed==32);
 for(int i=0;i<16;i++)assert(gObjectEvents[i].active);
 return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(fixture)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)

if __name__=='__main__':unittest.main()
