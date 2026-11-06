"""Agent-authored XL character geometry and native parser checks."""
import tempfile,unittest
from pathlib import Path
from world import xl_wilds_cast
from world.shared_cave import SharedCave,CaveError

def proposal():
 return {'rows':['#'*127]+['#'+'.'*125+'#']*125+['#'*127],'spawn':[1,1],'exit':[125,125]}
class XLCast(unittest.TestCase):
 def test_roundtrip_variable_positions_and_safe_literal_dialogue(self):
  cast=[{'gfx':7,'x':2,'y':1,'text':'Hello!'}, {'gfx':8,'x':80,'y':20,'text':'Far away!'}]
  blob=xl_wilds_cast.encode(proposal(),cast);self.assertEqual(xl_wilds_cast.validate_wire(blob),(proposal(),cast))
  self.assertEqual(len(blob),16321)
  with self.assertRaises(CaveError):SharedCave(blob)
  for bad in ([{**cast[0],'text':'<script>'}], [{**cast[0],'x':125,'y':125}], [cast[0],cast[0]], [{**cast[0],'gfx':42}]):
   with self.assertRaises(ValueError):xl_wilds_cast.encode(proposal(),bad)
 def test_cast_cannot_seal_entrance(self):
  cast=[{'gfx':7,'x':2,'y':1,'text':'Hi!'}, {'gfx':8,'x':1,'y':2,'text':'Hello!'}]
  with self.assertRaises(ValueError):xl_wilds_cast.encode(proposal(),cast)
 def test_production_c_validates_variable_cast_and_connectivity(self):
  import subprocess
  from test_save_isolation import function
  root=Path(__file__).resolve().parents[2];src=(root/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define XL_SIDE 127
#define XL_CELLS (127*127)
#define GENERATED_MAP_READY 1
#define GENERATED_WORLD_XL 1
#define GENERATED_WILDS_CAST 1
#define GENERATED_GUIDE_BYTES 59
#define GENERATED_CAST_BYTES 184
static u8 gGeneratedWildsGuideText[58],gGeneratedWildsCastText2[58],gGeneratedWildsCastText3[58],sCastMetadata[184];static int sXLCastStaged;
static int WorldBridge_Enabled(void){return 0;}static int GeneratedMap_IsInside(void){return 0;}static int GeneratedMap_EntryPending(void){return 0;}
static int GeneratedMap_StageXLWilds(const u8 *p,u32 n){return p&&n==16129;}
'''+'\n'.join(function(src,n) for n in ('ValidateGuideText','EncodeGuideText','GeneratedMap_StageXLCast'))+r'''
int main(void){u8 meta[184],cells[16129];assert(fread(meta,1,184,stdin)==184);assert(fread(cells,1,16129,stdin)==16129);
assert(GeneratedMap_StageXLCast(meta,184,cells,16129));assert(sXLCastStaged && sCastMetadata[1+61+1]==80);meta[1+61+1]=125;meta[1+61+2]=125;
assert(!GeneratedMap_StageXLCast(meta,184,cells,16129));return 0;}'''
  cast=[{'gfx':7,'x':2,'y':1,'text':'Hello!'},{'gfx':8,'x':80,'y':20,'text':'Far away!'}];blob=xl_wilds_cast.encode(proposal(),cast)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],input=blob[8:],capture_output=True);self.assertEqual(q.returncode,0,q.stderr.decode())
 def test_native_loader_accepts_only_exact_cast_file(self):
  import subprocess
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
#define GENERATED_WILDS_GUIDE 1
#define GENERATED_WILDS_CAST 1
#define GENERATED_WILDS_EVENTS 0
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_XL_MAP_BYTES 16129
#define GENERATED_CAST_BYTES 184
#define GENERATED_GUIDE_BYTES 59
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES 3969
static int calls;static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageLargeTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageWildsTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageXLWilds(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageGuidedWilds(const u8 *p,unsigned n,const u8 *c,unsigned z){(void)p;(void)n;(void)c;(void)z;return 0;}
static int GeneratedMap_StageCastWilds(const u8 *p,unsigned n,const u8 *c,unsigned z){(void)p;(void)n;(void)c;(void)z;return 0;}
static int GeneratedMap_StageXLCast(const u8 *p,unsigned n,const u8 *c,unsigned z){calls++;return n==184&&z==16129&&p[0]==1&&c[0]=='#';}
'''+function(src,'LoadGeneratedMapTemplate')+r'''
int main(int argc,char **argv){if(argc!=4)return 1;if(!LoadGeneratedMapTemplate(argv[1])||calls!=1)return 2;if(LoadGeneratedMapTemplate(argv[2])||calls!=1)return 3;if(LoadGeneratedMapTemplate(argv[3])||calls!=1)return 4;return 0;}'''
  cast=[{'gfx':7,'x':2,'y':1,'text':'Hello!'}];blob=xl_wilds_cast.encode(proposal(),cast)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code)
   for n,b in [('good',blob),('short',blob[:-1]),('long',blob+b'x')]:(p/n).write_bytes(b)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test'),str(p/'good'),str(p/'short'),str(p/'long')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
