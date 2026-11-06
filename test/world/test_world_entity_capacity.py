"""Production allocator/save-boundary tests with disposable engine stubs.

Not a native build or multiplayer gameplay acceptance test.
"""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function, PREAMBLE as SAVE_PREAMBLE
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
#define OBJECT_EVENTS_COUNT 48
#else
#define OBJECT_EVENTS_COUNT 16
#endif
struct ObjectEvent { int active,localId,mapNum,mapGroup,marker; };
struct SaveBlock { struct ObjectEvent objectEvents[SAVED_OBJECT_EVENTS_COUNT]; int sentinel; } save, *gSaveBlock1Ptr=&save;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
static bool8 sWorldObjectAllocation;
#endif
int cleanupCalls, cleanupSawExtended;
void WorldBridge_PrepareSave(void) {
    cleanupCalls++;
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
    if (gObjectEvents[16].active) cleanupSawExtended=1;
#endif
}
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
 for(int i=17;i<48;i++){gObjectEvents[i].active=1;gObjectEvents[i].localId=i+200;}
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
 gObjectEvents[16].active=1;gObjectEvents[47].active=1;
#endif
 LoadObjectEvents();for(int i=0;i<16;i++)assert(gObjectEvents[i].marker==100+i);
#if defined(PORTABLE) && WORLD_EXTENDED_OBJECTS
 assert(!gObjectEvents[16].active && !gObjectEvents[47].active);
 assert(cleanupCalls==2 && cleanupSawExtended);
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
   for flags in (['-DPORTABLE','-DWORLD_EXTENDED_OBJECTS=1'],['-DPORTABLE','-DWORLD_EXTENDED_OBJECTS=0'],['-DWORLD_EXTENDED_OBJECTS=1'],[]):
    subprocess.run(['cc','-std=c99','-Wall','-Werror',*flags,str(p/'t.c'),'-o',str(p/'t')],check=True)
    subprocess.run([str(p/'t')],check=True)
 def test_load_tears_down_owned_extended_sprite_before_clearing_slot(self):
  bridge=(ROOT/'src/platform/world_bridge.c').read_text();load=(ROOT/'src/load_save.c').read_text()
  fixture=SAVE_PREAMBLE.replace('#define WB_PEERS 8','#define WB_PEERS 16').replace('#define WB_LOCALID 224','#define WB_LOCALID 160').replace('#define OBJECT_EVENTS_COUNT 16','#define OBJECT_EVENTS_COUNT 48').replace('#define MAX_SPRITES 64','#define MAX_SPRITES 96').replace('struct ObjectEvent objectEvents[OBJECT_EVENTS_COUNT]','struct ObjectEvent objectEvents[SAVED_OBJECT_EVENTS_COUNT]')
  state=bridge[bridge.index('struct Peer {'):bridge.index('static bool8 Identifier(')]
  helpers=''.join(function(bridge,n) for n in ('Owned','RemoveRemote','SameGrid','GridCoords','Raw','RestoreTiles','WorldBridge_PrepareSave'))
  rally=(ROOT/'include/platform/world_rally.h').read_text();rally=rally[rally.index('#define WORLD_RALLY_ROSTER'):rally.index('/* Main/game thread only.')]
  code=fixture+rally+state+helpers+function(load,'LoadObjectEvents')+r"""
int main(void){
 sWorld.enabled=TRUE;gMapHeader.mapLayout=&layout;gBackupMapLayout.map=sBackupMapData;
 strcpy(sWorld.remotes[0].id,"bob");sWorld.remotes[0].object=16;sWorld.remotes[0].sprite=16;
 gObjectEvents[16].active=1;gObjectEvents[16].localId=WB_LOCALID;gObjectEvents[16].spriteId=16;
 gSprites[16].inUse=1;gSprites[16].data[0]=16;gSprites[16].data[7]=WB_MARKER;
 assert(Owned(0));LoadObjectEvents();assert(!gSprites[16].inUse);assert(!gObjectEvents[16].active);assert(!sWorld.remotes[0].id[0]);return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror','-Wno-unused-function','-DPORTABLE','-DUBFIX','-DWORLD_EXTENDED_OBJECTS=1',str(p/'t.c'),'-o',str(p/'t')],check=True)
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
   self.assertEqual(outputs[0][:3],outputs[1][:3]);self.assertEqual(outputs[0][3],'16');self.assertEqual(outputs[1][3],'48')
 def test_build_exposes_gate_to_both_preprocessor_and_compiler(self):
  makefile=(ROOT/'Makefile').read_text()
  self.assertIn('WORLD_EXTENDED_OBJECTS ?= 0',makefile)
  self.assertRegex(makefile,r'CPPFLAGS \+= [^\n]*-DWORLD_EXTENDED_OBJECTS=\$\(WORLD_EXTENDED_OBJECTS\)')
  self.assertRegex(makefile,r'override CFLAGS \+= -DWORLD_EXTENDED_OBJECTS=\$\(WORLD_EXTENDED_OBJECTS\)')
 def test_save_layout_remains_at_original_count(self):
  header=(ROOT/'include/global.h').read_text();self.assertIn('struct ObjectEvent objectEvents[SAVED_OBJECT_EVENTS_COUNT]',header)
  constants=(ROOT/'include/constants/global.h').read_text();self.assertIn('#define SAVED_OBJECT_EVENTS_COUNT 16',constants)

if __name__=='__main__':unittest.main()
