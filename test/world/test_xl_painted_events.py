"""Offline agent-painted XL story maps with character and connectivity checks."""
import subprocess,tempfile,unittest
from pathlib import Path
from test_save_isolation import function
from test_xl_wilds_cast import proposal
from test_xl_wilds_events import CAST,EVENTS
from world import xl_painted_events
ROOT=Path(__file__).resolve().parents[2]
class PaintedEvents(unittest.TestCase):
 def test_compiles_both_palette_and_graph_and_rejects_obstructed_character(self):
  paint=[{'x':30,'y':30,'width':10,'height':5,'terrain':'tall_grass'},{'x':80,'y':80,'width':3,'height':3,'terrain':'water'}]
  b=xl_painted_events.encode(proposal(),paint,CAST,EVENTS);self.assertEqual(b[:8],b'EWGMAP0E');self.assertEqual(len(b),17787);self.assertEqual(b[-16129+30*127+30],ord('t'))
  with self.assertRaises(ValueError):xl_painted_events.encode(proposal(),[{'x':75,'y':20,'width':1,'height':1,'terrain':'water'}],CAST,EVENTS)
 def test_production_c_composition_validates_and_stages_palette(self):
  src=(ROOT/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_WORLD_XL 1
#define GENERATED_WILDS_EVENTS 1
#define XL_CELLS 16129
#define XL_SIDE 127
static u8 sXLPalette[XL_CELLS];static bool8 sXLHasPalette;static int calls;
static int GeneratedMap_StageXLEvents(const u8 *e,u32 n,const u8 *c,u32 z,const u8 *g,u32 size){(void)e;(void)n;(void)c;(void)z;calls++;return size==XL_CELLS&&g[20*127+30]=='.';}
'''+function(src,'GeneratedMap_StageXLPaintedEvents')+r'''
int main(void){u8 e[1]={0},c[1]={0},p[XL_CELLS];memset(p,'.',sizeof(p));p[20*127+30]='t';assert(GeneratedMap_StageXLPaintedEvents(e,1,c,1,p,sizeof(p)));assert(sXLHasPalette&&sXLPalette[20*127+30]=='t'&&calls==1);p[128]='t';assert(!GeneratedMap_StageXLPaintedEvents(e,1,c,1,p,sizeof(p))&&calls==1);return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
 def test_explicit_atomic_replacement_and_default_no_overwrite(self):
  import json
  from unittest.mock import patch
  doc={'blueprint':{'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0},'paint':[],'cast':CAST,'events':EVENTS}
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);src=p/'in.json';out=p/'out.bin';src.write_text(json.dumps(doc));out.write_bytes(b'old')
   with patch('builtins.print'):
    with self.assertRaises(FileExistsError):xl_painted_events.main([str(src),str(out)])
    self.assertEqual(out.read_bytes(),b'old');xl_painted_events.main([str(src),str(out),'--replace-output'])
   self.assertEqual(out.read_bytes()[:8],b'EWGMAP0E')
