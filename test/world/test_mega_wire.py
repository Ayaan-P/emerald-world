"""Exercise the source packet codec; no socket or native runtime involved."""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
class MegaWireTest(unittest.TestCase):
 def test_roundtrip_and_reject_bad_headers_or_stale_generation(self):
  source=r'''
#include <stdint.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint8_t bool8;
#define FALSE 0
#define TRUE 1
#include "platform/mega_wire.h"
#include <assert.h>
int main(void){
 u8 p[16]={0},q[16];MegaWire_Encode(p,32,4,MEGA_WIRE_ACTIVATE,3,0x12345678);
 assert(MegaWire_IsCandidate(p,16,32));assert(MegaWire_Valid(p,16,32,17,0x12345678));
 assert(!MegaWire_Valid(p,12,32,17,0x12345678));assert(!MegaWire_Valid(p,16,32,17,0x12345679));
 for(int i=0;i<16;i++){for(int j=0;j<16;j++)q[j]=p[j];q[i]^=0x80;
   if(i!=5 && i!=6 && i!=7)assert(!MegaWire_Valid(q,16,32,17,0x12345678));}
 p[5]=0;assert(!MegaWire_Valid(p,16,32,17,0x12345678));
 p[5]=17;assert(!MegaWire_Valid(p,16,32,17,0x12345678));
 p[5]=4;p[7]=6;assert(!MegaWire_Valid(p,16,32,17,0x12345678));
 p[7]=3;p[6]=3;assert(!MegaWire_Valid(p,16,32,17,0x12345678));
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   path=Path(d);(path/'test.c').write_text(source)
   p=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror','-I',str(ROOT/'include'),str(path/'test.c'),'-o',str(path/'test')],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run([str(path/'test')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
if __name__=='__main__':unittest.main()
