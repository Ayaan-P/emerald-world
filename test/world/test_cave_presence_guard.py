"""A stale cave coordinate is never published before this connection is ready."""
from pathlib import Path
from test_save_isolation import function
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CavePresenceGuard(unittest.TestCase):
 def test_send_state_clears_stale_cave_anchor(self):
  src=(ROOT/'src/platform/world_bridge.c').read_text()
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define OBJ_EVENT_GFX_BOY_1 7
struct Peer {unsigned group,num,x,y,facing,gfx,ready;};
static struct {int connected,fieldKnown,menuAnchor;unsigned seq,outputSize;char output[512];struct Peer field;} sWorld;
struct Save {char bagPocket_Items[1],bagPocket_KeyItems[1],bagPocket_PokeBalls[1],bagPocket_TMHM[1],bagPocket_Berries[1];} save,*gSaveBlock1Ptr=&save;
char gPlayerParty[16];static int inside=1,caveReady=0;
int GeneratedMap_IsInside(void){return inside;}
int WorldBridge_GeneratedCaveReady(void){return caveReady;}
int Overworld(void){return 1;}int PresenceReady(void){return 1;}int WorldActivity_IsEncounterPending(void){return 0;}
void Fingerprint(const void *p,unsigned long n,char out[17]){(void)p;(void)n;strcpy(out,"aaaaaaaaaaaaaaaa");}
void Flush(void){}
'''+function(src,'SendState')+r'''
int main(void){sWorld.connected=1;sWorld.fieldKnown=sWorld.menuAnchor=1;sWorld.field=(struct Peer){34,0,5,5,1,7,1};SendState();
 assert(!sWorld.fieldKnown&&!sWorld.menuAnchor);assert(strstr(sWorld.output,"STATE 1 0 0 0 0 1 7 0 "));
 sWorld.outputSize=0;sWorld.fieldKnown=1;caveReady=1;SendState();assert(sWorld.fieldKnown);assert(strstr(sWorld.output,"STATE 2 34 0 5 5 1 7 1 "));return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
