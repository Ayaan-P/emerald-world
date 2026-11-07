"""Production native XL graph identity matches SHA-256 of canonical bytes."""
import hashlib,subprocess,tempfile,unittest
from pathlib import Path
from test_xl_wilds_cast import proposal
from test_xl_wilds_events import CAST,EVENTS
from world.xl_wilds_events import encode
from world.xl_painted_events import encode as encode_painted
ROOT=Path(__file__).resolve().parents[2]
class XLStoryHash(unittest.TestCase):
 def test_production_digest_matches_python_and_tracks_every_component(self):
  code=r'''#include <stdio.h>
#include <stdint.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(int argc,char **argv){u8 e[1466],c[184],m[16129];char hex[65];if(argc!=2||fread(e,1,1466,stdin)!=1466||fread(c,1,184,stdin)!=184||fread(m,1,16129,stdin)!=16129)return 1;if(argv[1][0]=='F')WorldCaveWire_XLStableStoryDigest(e,c,m,hex);else if(argv[1][0]=='E')WorldCaveWire_XLPaintedEventDigest(e,c,m,hex);else WorldCaveWire_XLEventDigest(e,c,m,hex);puts(hex);return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   base=encode(proposal(),CAST,EVENTS)
   for offset in (None,10,8+1466+5,8+1466+184+500):
    blob=bytearray(base)
    if offset is not None:blob[offset]^=1
    q=subprocess.run([str(p/'test'),'C'],input=bytes(blob[8:]),capture_output=True);self.assertEqual(q.returncode,0,q.stderr.decode());self.assertEqual(q.stdout.decode().strip(),hashlib.sha256(blob).hexdigest())
   painted=encode_painted(proposal(),[{'x':30,'y':30,'width':2,'height':2,'terrain':'tall_grass'}],CAST,EVENTS)
   for offset in (None,10,8+1466+5,8+1466+184+500):
    blob=bytearray(painted)
    if offset is not None:blob[offset]^=1
    q=subprocess.run([str(p/'test'),'E'],input=bytes(blob[8:]),capture_output=True);self.assertEqual(q.returncode,0,q.stderr.decode());self.assertEqual(q.stdout.decode().strip(),hashlib.sha256(blob).hexdigest())
   events=painted[8:8+1466];cast=painted[8+1466:8+1466+184];world_id=b'1'*16
   q=subprocess.run([str(p/'test'),'F'],input=events+cast+world_id+bytes(16129-16),capture_output=True);self.assertEqual(q.returncode,0,q.stderr.decode());self.assertEqual(q.stdout.decode().strip(),hashlib.sha256(b'EWGMAP0F'+events+cast+world_id).hexdigest())
 def test_invalid_serialized_identity_is_rejected(self):
  from test_save_isolation import function
  src=(ROOT/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define XL_PROGRESS_SLOTS 64
#define XL_PROGRESS_SLOT_BYTES 70
static u8 sXLProgressPayload[1+64*70],sXLProgressNext;
static struct {bool8 valid;u8 trainer[4],state,identity[64];} sXLProgress[64];
'''+function(src,'XLProgressUnpack')+r'''
int main(void){sXLProgressPayload[1]=1;memset(sXLProgressPayload+7,'g',64);assert(!XLProgressUnpack());memset(sXLProgressPayload+7,'a',64);assert(XLProgressUnpack());sXLProgressPayload[6]=16;assert(!XLProgressUnpack());return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
