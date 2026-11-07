"""Exercise actual RC7 shuffle with world override and local restore, no sockets."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))

class WorldShuffle(unittest.TestCase):
    def test_world_overrides_and_restores_local_choice(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / 'gba').mkdir()
            (p / 'gba/types.h').write_text('#include <stdint.h>\ntypedef uint8_t bool8;typedef uint16_t u16;typedef uint32_t u32;\n')
            (p / 'global.h').write_text('#include "gba/types.h"\n#define TRUE 1\n#define FALSE 0\n')
            (p / 'pokemon.h').write_text('#include "gba/types.h"\nu16 SpeciesToNationalPokedexNum(u16);u16 NationalPokedexNumToSpecies(u16);\n')
            (p / 'test.c').write_text(r'''
#include <assert.h>
#include "platform/wild_shuffle.h"
u16 SpeciesToNationalPokedexNum(u16 s){return s;}
u16 NationalPokedexNumToSpecies(u16 n){return n;}
int main(void){
 assert(!WildShuffle_Enabled());
 WildShuffle_Toggle(); WildShuffle_NextSeed();
 assert(WildShuffle_Enabled() && WildShuffle_Seed()==2);
 u16 local=WildShuffle_MapNational(25);
 WildShuffle_SetWorldRule(0,7);
 assert(WildShuffle_WorldManaged() && !WildShuffle_Enabled() && WildShuffle_Seed()==7);
 assert(WildShuffle_MapNational(25)==25);
 WildShuffle_Toggle(); WildShuffle_NextSeed();
 assert(!WildShuffle_Enabled() && WildShuffle_Seed()==7);
 WildShuffle_SetWorldRule(1,7);
 assert(WildShuffle_Enabled() && WildShuffle_Seed()==7);
 u16 remote=WildShuffle_MapNational(25); assert(remote!=25);
 WildShuffle_SetWorldRule(1,0); assert(WildShuffle_Seed()==7);
 WildShuffle_ClearWorldRule();
 assert(!WildShuffle_WorldManaged() && WildShuffle_Enabled() && WildShuffle_Seed()==2);
 assert(WildShuffle_MapNational(25)==local);
 return 0;
}''')
            q = subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-DPORTABLE',
                                '-I'+str(p),'-I'+str(ENGINE/'include'),
                                str(ENGINE/'src/world/wild_shuffle.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q = subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
