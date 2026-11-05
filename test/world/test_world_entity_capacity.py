"""Production allocator/save-boundary tests with disposable engine stubs.

Not a native build or multiplayer gameplay acceptance test.
"""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]

PREAMBLE=r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int bool8;
#define TRUE 1
#define FALSE 0
#define SAVED_OBJECT_EVENTS_COUNT 16
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
#define OBJECT_EVENTS_COUNT 32
#else
#define OBJECT_EVENTS_COUNT 16
#endif
struct ObjectEvent { int active,localId,mapNum,mapGroup,marker; };
struct SaveBlock { struct ObjectEvent objectEvents[SAVED_OBJECT_EVENTS_COUNT]; int sentinel; } save, *gSaveBlock1Ptr=&save;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
static bool8 sWorldObjectAllocation;
#endif
void WorldBridge_PrepareSave(void) {}
"""
MAIN=r"""
int main(void) {
 u8 id=99;
 for(int i=0;i<16;i++){gObjectEvents[i].active=1;gObjectEvents[i].localId=i;gObjectEvents[i].marker=100+i;}
 assert(GetFirstInactiveObjectEventId()==OBJECT_EVENTS_COUNT);
 assert(GetAvailableObjectEventId(200,1,1,&id));
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
 sWorldObjectAllocation=TRUE;
 assert(!GetAvailableObjectEventId(200,1,1,&id) && id==16);
 gObjectEvents[16].active=1;gObjectEvents[16].localId=200;gObjectEvents[16].mapNum=1;gObjectEvents[16].mapGroup=1;
 assert(GetAvailableObjectEventId(200,1,1,&id));
 sWorldObjectAllocation=FALSE;assert(GetAvailableObjectEventId(201,1,1,&id));
 sWorldObjectAllocation=TRUE;
 for(int i=17;i<32;i++){gObjectEvents[i].active=1;gObjectEvents[i].localId=i+200;}
 assert(GetAvailableObjectEventId(210,9,9,&id));
 gObjectEvents[5].active=0;
 assert(!GetAvailableObjectEventId(210,9,9,&id) && id==5);
 gObjectEvents[5].active=1;
 gObjectEvents[16].active=0;
 gObjectEvents[20].mapNum=2;gObjectEvents[20].mapGroup=3;
 assert(GetAvailableObjectEventId(gObjectEvents[20].localId,2,3,&id));
 sWorldObjectAllocation=FALSE;
#endif
 save.sentinel=0x123456;SaveObjectEvents();assert(save.sentinel==0x123456);
 for(int i=0;i<16;i++) assert(save.objectEvents[i].marker==100+i);
 memset(gObjectEvents,0,sizeof(gObjectEvents));
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
 gObjectEvents[16].active=1;gObjectEvents[31].active=1;
#endif
 LoadObjectEvents();for(int i=0;i<16;i++)assert(gObjectEvents[i].marker==100+i);
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
 assert(!gObjectEvents[16].active && !gObjectEvents[31].active);
#endif
 return 0;
}
"""
class EntityCapacity(unittest.TestCase):
 def test_actual_pool_and_save_copy(self):
  move=(ROOT/'src/event_object_movement.c').read_text();save=(ROOT/'src/load_save.c').read_text()
  a=move.index('static bool8 GetAvailableObjectEventId(u16 localId, u8 mapNum, u8 mapGroup, u8 *objectEventId)\n// Looks')
  b=move.index('\nstatic void RemoveObjectEvent(',a)
  source=PREAMBLE+function(move,'GetFirstInactiveObjectEventId')+move[a:b]+function(save,'SaveObjectEvents')+function(save,'LoadObjectEvents')+MAIN
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source)
   for flags in (['-DPORTABLE','-DWORLD_EXTENDED_OBJECTS=1'],['-DPORTABLE','-DWORLD_EXTENDED_OBJECTS=0'],[]):
    subprocess.run(['cc','-std=c99','-Wall','-Werror',*flags,str(p/'t.c'),'-o',str(p/'t')],check=True)
    subprocess.run([str(p/'t')],check=True)
 def test_real_saveblock_layout_matches_gate_off(self):
  code = r"""
#include <stddef.h>
#include <stdio.h>
#include "global.h"
int main(void) {
 printf("%zu %zu %zu %d\\n", sizeof(struct SaveBlock1), offsetof(struct SaveBlock1, objectEventTemplates), sizeof(((struct SaveBlock1*)0)->objectEvents), OBJECT_EVENTS_COUNT);
 return 0;
}
""".replace(r"\\n", r"\n")
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'layout.c').write_text(code);outputs=[]
   for gate in ('0','1'):
    subprocess.run(['cc','-std=gnu11','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),'-DPORTABLE','-DNONMATCHING','-DUBFIX','-DWORLD_EXTENDED_OBJECTS='+gate,str(p/'layout.c'),'-o',str(p/'layout')],check=True)
    outputs.append(subprocess.check_output([str(p/'layout')],text=True).split())
   self.assertEqual(outputs[0][:3],outputs[1][:3]);self.assertEqual(outputs[0][3],'16');self.assertEqual(outputs[1][3],'32')
 def test_save_layout_remains_at_original_count(self):
  header=(ROOT/'include/global.h').read_text();self.assertIn('struct ObjectEvent objectEvents[SAVED_OBJECT_EVENTS_COUNT]',header)
  constants=(ROOT/'include/constants/global.h').read_text();self.assertIn('#define SAVED_OBJECT_EVENTS_COUNT 16',constants)

if __name__=='__main__':unittest.main()
