"""Compile production native cave frame and SHA checks against a fixture."""
from pathlib import Path
import hashlib,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CaveWireTests(unittest.TestCase):
 def test_hash_matches_python_for_varied_payloads(self):
  import random
  code=r"""
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[256];struct WorldCaveWire w={0};int result=0;
 while(fgets(line,sizeof(line),stdin)){char *tokens[5],*save,*p;unsigned n=0;
  line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))tokens[n++]=p;
  result=WorldCaveWire_Feed(&w,n,(const char *const*)tokens);if(result<0)return 2;
 }return result==1?0:3;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   from world.shared_cave import SharedCave
   valid=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
   authority=SharedCave(b'EWGMAP01'+''.join(valid).encode())
   q=subprocess.run([str(p/'test')],input=authority.frames(),capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   rng=random.Random(2026)
   for _ in range(40):
    rows=[''.join(rng.choice('.#') for _ in range(31)) for _ in range(31)]
    digest=hashlib.sha256(b'EWGMAP01'+''.join(rows).encode()).hexdigest()
    frames=[f'CAVE BEGIN {digest}']+[f'CAVE ROW {digest} {i} {row}' for i,row in enumerate(rows)]+[f'CAVE END {digest}']
    q=subprocess.run([str(p/'test')],input='\n'.join(frames)+'\n',capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
 def test_valid_and_invalid_streams(self):
  rows=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
  identity=hashlib.sha256(b'EWGMAP01'+''.join(rows).encode()).hexdigest()
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){
 struct WorldCaveWire w={0};const char *id="IDENTITY";
 const char *begin[]={"CAVE","BEGIN",id};const char *end[]={"CAVE","END",id};
 const char *row[]={"CAVE","ROW",id,"0","###############################"};
 assert(WorldCaveWire_Feed(&w,3,begin)==0);
 assert(WorldCaveWire_Feed(&w,3,begin)==-1); /* duplicate begin */
 assert(WorldCaveWire_Feed(&w,3,end)==-1); /* incomplete */
 for(int i=0;i<31;i++){
  char index[4];snprintf(index,sizeof(index),"%d",i);row[3]=index;
  row[4]=(i==0||i==30)?"###############################":"#.............................#";
  assert(WorldCaveWire_Feed(&w,5,row)==0);
 }
 assert(WorldCaveWire_Feed(&w,3,end)==1 && !w.active);
 WorldCaveWire_Reset(&w);assert(WorldCaveWire_Feed(&w,3,begin)==0);
 for(int i=0;i<31;i++){
  char index[4];snprintf(index,sizeof(index),"%d",i);row[3]=index;
  row[4]=(i==0||i==30)?"###############################":"#.............................#";
  if(i==1) row[4]="#............................##"; /* valid syntax, wrong digest */
  assert(WorldCaveWire_Feed(&w,5,row)==0);
 }
 assert(WorldCaveWire_Feed(&w,3,end)==-1);
 WorldCaveWire_Reset(&w);assert(WorldCaveWire_Feed(&w,3,begin)==0);
 row[3]="01";assert(WorldCaveWire_Feed(&w,5,row)==-1);
 assert(WorldCaveWire_Feed(&w,6,row)==-1);
 return 0;
}'''.replace('IDENTITY',identity)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
