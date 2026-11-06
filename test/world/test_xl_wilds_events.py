"""Bounded offline XL interaction graphs, tested without provider calls."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
from test_xl_wilds_cast import proposal
from world import xl_wilds_events
CAST=[{'gfx':7,'x':2,'y':1,'text':'Hello!'},{'gfx':8,'x':75,'y':20,'text':'Far away!'}]
EVENTS={'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Find my friend.'},{'state':1,'npc':2,'next':2,'text':'I am fine!'}]}
class XLEvents(unittest.TestCase):
 def test_compiles_inert_xl_graph_and_rejects_bad_rules(self):
  blob=xl_wilds_events.encode(proposal(),CAST,EVENTS);self.assertEqual(blob[:8],b'EWGMAP0C');self.assertEqual(len(blob),17787)
  for bad in ({'initial':0,'rules':[EVENTS['rules'][0],EVENTS['rules'][0]]},{'initial':0,'rules':[{'state':0,'npc':3,'next':1,'text':'x'}]},{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'<script>'}]}):
   with self.assertRaises(ValueError):xl_wilds_events.encode(proposal(),CAST,bad)
 def test_production_c_rejects_duplicate_or_unsafe_rules(self):
  root=Path(__file__).resolve().parents[2];src=(root/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef uint32_t u32;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_WORLD_XL 1
#define GENERATED_WILDS_EVENTS 1
#define GENERATED_EVENT_BYTES 1466
#define GENERATED_CAST_BYTES 184
#define GENERATED_GUIDE_BYTES 59
static u8 sEventData[1466];static int sEventStaged;
static int GeneratedMap_StageXLCast(const u8 *p,u32 n,const u8 *c,u32 z){return p&&n==184&&c&&z==16129;}
'''+function(src,'ValidateGuideText')+'\n'+function(src,'ValidateEventRules')+'\n'+function(src,'GeneratedMap_StageXLEvents')+r'''
int main(void){u8 events[1466],cast[184],cells[16129];assert(fread(events,1,1466,stdin)==1466);assert(fread(cast,1,184,stdin)==184);assert(fread(cells,1,16129,stdin)==16129);
assert(GeneratedMap_StageXLEvents(events,1466,cast,184,cells,16129)&&sEventStaged);memcpy(events+63,events+2,61);assert(!GeneratedMap_StageXLEvents(events,1466,cast,184,cells,16129));return 0;}'''
  blob=xl_wilds_events.encode(proposal(),CAST,EVENTS)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],input=blob[8:],capture_output=True);self.assertEqual(q.returncode,0,q.stderr.decode())
