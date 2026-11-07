"""XL authority and actual native wire parser; no socket access required."""
from pathlib import Path
import base64, json, os, subprocess, tempfile, unittest
from test_shared_generated_cave import MemoryAuthority
from world.shared_cave import SharedCave
from world.xl_wilds import encode
ROOT=Path(__file__).resolve().parents[2]
ENGINE=Path(os.environ.get("EW_RC7_ENGINE", ROOT / "engines/expansion-native"))

def blob():
    rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
    return encode({'rows':rows,'spawn':[1,1],'exit':[125,125]})

class SharedXL(unittest.TestCase):
 def test_authority_capability_and_two_trainers(self):
  cave=SharedCave(blob())
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);s=MemoryAuthority(p/'socket',p/'world',cave_template=blob())
   try:
    def connect(name,cap):
     ident=s.create_identity(name);c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
     s._line(c,f"HELLO 1 {name} {ident['token']} SOCIALTRAVELCHATRALLY{cap}".encode());self.assertIn(b'WELCOME 1',c['out']);c['out'].clear();return c
    a=connect('Alice','CAVE16');b=connect('Bob','CAVE16');old=connect('Old','CAVE10')
    for c in (a,b):
     s._line(c,b'CAVE GET');self.assertEqual(c['out'].decode(),cave.frames());c['out'].clear()
     s._line(c,('CAVE ACK '+cave.identity).encode());self.assertIn(b'CAVE OK',c['out']);c['out'].clear()
     g,n=s.wilds_map;s._line(c,(f'STATE 1 {g} {n} 100 100 1 7 1 '+('a'*16)+' '+('b'*16)).encode());self.assertFalse(c['closing']);self.assertEqual(c['state'][2:4],[100,100])
    s._line(old,b'CAVE GET');self.assertEqual(old['out'],b'CAVE NONE\n')
   finally:s.close()
 def test_owner_admin_can_publish_full_xl_blob(self):
  from world.server import MAX_ADMIN_LINE, MAX_CONTROL_LINE
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);s=MemoryAuthority(p/'socket',p/'world')
   try:
    raw=json.dumps({'command':'replace_cave','template':base64.b64encode(blob()).decode()}).encode()
    self.assertGreater(len(raw),MAX_CONTROL_LINE);self.assertLess(len(raw),MAX_ADMIN_LINE)
    c={'out':bytearray(),'closing':False};s._admin_line(c,raw)
    result=json.loads(c['out']);self.assertTrue(result['ok']);self.assertEqual(result['id'],SharedCave(blob()).identity)
   finally:s.close()
 def test_native_wire_and_corruption(self):
  code=r'''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[256];struct WorldCaveWire w={0};int r=0;
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}return r==1&&w.version==16&&w.nextRow==127?0:3;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_WORLD_XL=1','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ENGINE/'src/world/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   frames=SharedCave(blob()).frames();run=lambda x:subprocess.run([str(p/'test')],input=x,text=True,capture_output=True).returncode
   self.assertEqual(run(frames),0)
   lines=frames.splitlines();lines[80]=lines[80][:-2]+'#'+lines[80][-1];self.assertNotEqual(run('\n'.join(lines)+'\n'),0)
   self.assertNotEqual(run('\n'.join(frames.splitlines()[:-2]+frames.splitlines()[-1:])+'\n'),0)
 def test_native_bridge_admits_only_negotiated_map(self):
  from test_save_isolation import function
  bridge=(ENGINE/'src/world/world_bridge.c').read_text()
  code=r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
enum CaveState {CAVE_DISABLED,CAVE_IDLE,CAVE_WAIT,CAVE_WAIT_RESET,CAVE_ACK,CAVE_WAIT_OK,CAVE_READY,CAVE_MISMATCH,CAVE_RETURN_NONE};
static struct {bool8 caveAvailable,staging,caveV16Probe;enum CaveState caveState;unsigned caveTimeout,caveRetry;char caveExpected[65];struct WorldCaveWire caveWire;} sWorld;
static int inside,matched,stageCount;
static int GeneratedMap_IsInside(void){return inside;}static int GeneratedMap_EntryPending(void){return 0;}
static int GeneratedMap_MatchesPreparedXLWilds(const u8 *p,unsigned n){(void)p;(void)n;return matched;}
static int GeneratedMap_StageSharedXLWilds(const u8 *p,unsigned n){(void)p;if(n!=16129)return 0;stageCount++;return 1;}
static int GeneratedMap_MatchesPrepared(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
''' + function(bridge,'CaveLine') + r'''
int main(int argc,char **argv){char line[256];int r=0;sWorld.caveAvailable=1;sWorld.caveState=CAVE_WAIT;sWorld.caveV16Probe=atoi(argv[1]);inside=atoi(argv[2]);matched=atoi(argv[3]);
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=CaveLine(n,t);if(!r)return 2;}return (int)sWorld.caveState==atoi(argv[4]) && stageCount==atoi(argv[5])?0:3;}
'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-DPORTABLE','-DGENERATED_WORLD_XL=1','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ENGINE/'src/world/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   frames=SharedCave(blob()).frames()
   def run(*args):return subprocess.run([str(p/'test'),*map(str,args)],input=frames,text=True,capture_output=True).returncode
   self.assertEqual(run(1,0,0,4,1),0) # staged and acknowledged
   self.assertEqual(run(1,1,0,7,0),0) # different active map must leave first
   self.assertEqual(run(1,1,1,4,0),0) # same map reconnects without restaging
   self.assertNotEqual(run(0,0,0,4,1),0) # no capability negotiation
