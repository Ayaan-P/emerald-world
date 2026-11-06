"""Agent-painted XL terrain is bounded, connected and offline-only."""
import unittest
from test_xl_wilds_cast import proposal
from world import xl_wilds_palette
from world.shared_cave import SharedCave,CaveError
class XLPalette(unittest.TestCase):
 def test_paint_rectangles_control_real_tiles(self):
  paint=[{'x':80,'y':20,'width':4,'height':3,'terrain':'tall_grass'}, {'x':82,'y':21,'width':1,'height':1,'terrain':'water'}]
  blob=xl_wilds_palette.encode(proposal(),paint);self.assertEqual(blob[:8],b'EWGMAP0D');self.assertEqual(blob[8+20*127+80],ord('t'));self.assertEqual(blob[8+21*127+82],ord('#'));self.assertEqual(blob[8+1*127+1],ord('.'))
  with self.assertRaises(CaveError):SharedCave(blob)
 def test_rejects_disconnection_protected_cells_and_bad_paint(self):
  for paint in ([{'x':1,'y':1,'width':1,'height':1,'terrain':'tall_grass'}],[{'x':1,'y':2,'width':125,'height':1,'terrain':'water'}],[{'x':1,'y':1,'width':0,'height':1,'terrain':'grass'}],[{'x':1,'y':1,'width':1,'height':1,'terrain':'code'}]):
   with self.assertRaises(ValueError):xl_wilds_palette.encode(proposal(),paint)
 def test_native_loader_accepts_only_exact_palette_file(self):
  import subprocess,tempfile
  from pathlib import Path
  from test_save_isolation import function
  root=Path(__file__).resolve().parents[2];src=(root/'src/platform/sdl2.c').read_text()
  code=r'''#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_MAP_LARGE 1
#define GENERATED_MAP_WILDS 1
#define GENERATED_WORLD_XL 1
#define GENERATED_WILDS_GUIDE 0
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_XL_MAP_BYTES 16129
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES 3969
#define GENERATED_WILDLIFE_BYTES 37
static int calls;static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageLargeTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageWildsTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageXLWilds(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageXLPalette(const u8 *p,unsigned n){calls++;return n==16129&&p[0]=='#';}
'''+function(src,'LoadGeneratedMapTemplate')+r'''
int main(int argc,char **argv){if(argc!=4)return 1;if(!LoadGeneratedMapTemplate(argv[1])||calls!=1)return 2;if(LoadGeneratedMapTemplate(argv[2])||calls!=1)return 3;if(LoadGeneratedMapTemplate(argv[3])||calls!=1)return 4;return 0;}'''
  blob=xl_wilds_palette.encode(proposal(),[{'x':80,'y':20,'width':2,'height':2,'terrain':'tall_grass'}])
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code)
   for n,b in [('good',blob),('short',blob[:-1]),('long',blob+b'x')]:(p/n).write_bytes(b)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test'),str(p/'good'),str(p/'short'),str(p/'long')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
