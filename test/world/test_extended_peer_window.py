"""Exercise authenticated relevance-window negotiation without sockets."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
from world.server import WorldServer

ROOT=Path(__file__).resolve().parents[2]
class MemoryServer(WorldServer):
 def _queue(self,c,text):c['out'].extend(text.encode())
 def _broadcast(self):pass

class ExtendedPeerWindow(unittest.TestCase):
 def test_legacy_and_opt_in_view_and_auth_boundary(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);server=MemoryServer(root/'s',root/'w');self.addCleanup(server.close)
   def connect(name,role):
    identity=server.create_identity(name)
    conn={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
    server._line(conn,('HELLO 1 '+name+' '+identity['token']+(' '+role if role else '')).encode())
    return conn
   legacy=connect('legacy','SOCIALTRAVELCHAT');extended=connect('extended','SOCIALTRAVELCHATPEER16')
   self.assertIn(b'WELCOME',legacy['out']);self.assertIn(b'WELCOME',extended['out'])
   for i in range(20):
    server.peers[f'P{i:02}']={'id':f'P{i:02}','closing':False,'state':[1,1,i+1,3,1,7,1],'field':True}
   for conn,want in ((legacy,8),(extended,16)):
    conn['state']=[1,1,0,3,1,7,1]
    peers=[line for line in server._snapshot(conn).splitlines() if line.startswith('PEER ')]
    self.assertEqual(len(peers),want)
    self.assertTrue(any(line.startswith('PEER P00 ') for line in peers))
   for index,role in enumerate(('CONTROLPEER16','LINKPEER16','PEER16','BADPEER16')):
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
struct {int connected,rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,peer16Probe,peer16Legacy;char output[256],trainer[25],token[65];int outputSize;} sWorld;
'''+queue+'\nstatic bool8 TestFallback(char **tokens, unsigned n)\n{\n'+fallback+r'''
int main(void){
 strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");QueueHello(0);
 assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYPEER16"));
 char *e[]={"ERROR","AUTH"};assert(!TestFallback(e,2));
 assert(sWorld.peer16Legacy && !sWorld.rallyLegacy && !sWorld.travelLegacy && !sWorld.chatLegacy);
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLY\n"));assert(!strstr(sWorld.output,"PEER16"));
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)

if __name__=='__main__':unittest.main()
