"""Check generated-cave capability negotiation and legacy fallback."""
from pathlib import Path
from test_save_isolation import function
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CaveHello(unittest.TestCase):
 def test_probe_then_fallback_without_removing_other_capabilities(self):
  src=(ROOT/'src/platform/world_bridge.c').read_text()
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
static struct {bool8 commandsProbe,commandsLegacy,rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,caveProbe,caveLegacy;char trainer[25],token[65],output[4096];int outputSize;} sWorld;
'''+function(src,'CaveProbeRejected')+function(src,'QueueHello')+r'''
int main(void){sWorld.commandsLegacy=1;char *err[]={"ERROR","AUTH"};strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYCAVE\n") && sWorld.caveProbe);
 assert(CaveProbeRejected(2,err)&&sWorld.caveLegacy);
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLY\n") && !sWorld.caveProbe);
 assert(!CaveProbeRejected(2,err));assert(sWorld.rallyProbe&&sWorld.travelProbe&&sWorld.chatProbe);
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
