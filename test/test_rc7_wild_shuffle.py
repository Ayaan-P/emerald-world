"""Compile and run the actual native wild shuffle without a game or sockets."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get("EW_RC7_ENGINE", ROOT / "engines/expansion-native"))

class WildShuffleTests(unittest.TestCase):
 def test_stable_permutation_opt_in_and_engine_conversion(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'gba').mkdir()
   (p/'gba/types.h').write_text('#include <stdint.h>\ntypedef uint8_t bool8;typedef uint16_t u16;typedef uint32_t u32;\n')
   (p/'global.h').write_text('#include "gba/types.h"\n')
   (p/'pokemon.h').write_text('#include "gba/types.h"\nu16 SpeciesToNationalPokedexNum(u16);u16 NationalPokedexNumToSpecies(u16);\n')
   (p/'test.c').write_text(r'''
#include <assert.h>
#include "platform/wild_shuffle.h"
/* Deliberately non-identical engine IDs exercise the canonical Dex boundary. */
u16 SpeciesToNationalPokedexNum(u16 s){return s>=1001 && s<=1386?s-1000:0;}
u16 NationalPokedexNumToSpecies(u16 n){return n>=1 && n<=386?n+1000:0;}
int main(void){
 unsigned seen[387]={0};u16 first[387];
 assert(!WildShuffle_Enabled());assert(WildShuffle_Seed()==1);
 for(unsigned i=1;i<=386;i++)assert(WildShuffle_MapNational(i)==i);
 assert(WildShuffle_MapSpecies(1025)==1025);
 WildShuffle_Toggle();assert(WildShuffle_Enabled());
 for(unsigned i=1;i<=386;i++){u16 n=WildShuffle_MapNational(i);assert(n>=1 && n<=386);assert(!seen[n]++);first[i]=n;assert(WildShuffle_MapSpecies(i+1000)==n+1000);}
 assert(first[1]==377 && first[2]==160 && first[3]==108 && first[25]==210 && first[150]==319 && first[252]==61 && first[386]==170);
 assert(WildShuffle_MapNational(0)==0 && WildShuffle_MapNational(387)==387);
 assert(WildShuffle_MapSpecies(999)==999);
 WildShuffle_NextSeed();assert(WildShuffle_Seed()==2);
 int changed=0;for(unsigned i=1;i<=386;i++)if(WildShuffle_MapNational(i)!=first[i])changed=1;assert(changed);
 for(int i=0;i<19;i++){WildShuffle_NextSeed();}
 assert(WildShuffle_Seed()==1);
 for(unsigned i=1;i<=386;i++)assert(WildShuffle_MapNational(i)==first[i]);
 WildShuffle_Toggle();for(unsigned i=1;i<=386;i++)assert(WildShuffle_MapNational(i)==i);
 return 0;
}
''')
   binary=p/'shuffle';build=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-DPORTABLE','-I'+str(p),'-I'+str(ROOT/'include'),str(ENGINE/'src/world/wild_shuffle.c'),str(p/'test.c'),'-o',str(binary)],capture_output=True,text=True)
   self.assertEqual(build.returncode,0,build.stderr)
   run=subprocess.run([str(binary)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
if __name__=='__main__':unittest.main()
