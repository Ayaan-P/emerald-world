"""Battle-only Mega form/ownership calculations with isolated native stubs.

This is not a playable feature or a native game build.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
class MegaBattleTests(unittest.TestCase):
    def test_form_ownership_and_stat_calculation(self):
        main=r'''
#include "global.h"
#include "constants/species.h"
#include "constants/pokemon.h"
#include "constants/abilities.h"
#include "platform/mega_battle.h"
#include <assert.h>
#include <string.h>
static u16 neutral(u8 n,u16 s,u8 i) {(void)n;(void)i;return s;}
static u16 attackUp(u8 n,u16 s,u8 i) {(void)n;return i==STAT_ATK?s*110/100:s;}
int main(void) {
 struct MegaBattleState state;struct MegaStatInput input={0};
 struct MegaBattleStats out={0},sentinel;
 const struct MegaFormData *form;
 MegaBattle_Reset(&state);
 assert(MegaForm_Find(SPECIES_VENUSAUR,MEGA_STONE_VENUSAURITE)==MEGA_FORM_VENUSAUR_MEGA);
 assert(MegaForm_Find(SPECIES_VENUSAUR,MEGA_STONE_GENGARITE)==MEGA_FORM_NONE);
 assert(!MegaBattle_Activate(&state,0,0,SPECIES_VENUSAUR,MEGA_STONE_VENUSAURITE,0,1));
 assert(!MegaBattle_Activate(&state,0,0,SPECIES_VENUSAUR,MEGA_STONE_VENUSAURITE,1,0));
 assert(MegaBattle_Activate(&state,0,0,SPECIES_VENUSAUR,MEGA_STONE_VENUSAURITE,1,1)==MEGA_FORM_VENUSAUR_MEGA);
 assert(!MegaBattle_Activate(&state,0,1,SPECIES_GENGAR,MEGA_STONE_GENGARITE,1,1));
 assert(MegaBattle_Activate(&state,1,0,SPECIES_GENGAR,MEGA_STONE_GENGARITE,1,1)==MEGA_FORM_GENGAR_MEGA);
 assert(MegaBattle_GetForm(&state,0,0)==MEGA_FORM_VENUSAUR_MEGA);
 assert(MegaBattle_GetForm(&state,1,0)==MEGA_FORM_GENGAR_MEGA);
 assert(!MegaBattle_GetForm(&state,4,0));
 form=MegaForm_Get(MEGA_FORM_VENUSAUR_MEGA);
 assert(form && form->baseHP==80 && form->ability==ABILITY_THICK_FAT);
 input.level=50;for(int i=0;i<5;i++){input.iv[i]=31;input.ev[i]=252;}
 assert(MegaForm_Calculate(MEGA_FORM_VENUSAUR_MEGA,&input,neutral,&out));
 assert(out.attack==152 && out.defense==175 && out.speed==132 && out.spAttack==174 && out.spDefense==172);
 assert(out.type1==TYPE_GRASS && out.type2==TYPE_POISON && out.ability==ABILITY_THICK_FAT);
 assert(MegaForm_Calculate(MEGA_FORM_VENUSAUR_MEGA,&input,attackUp,&out));
 assert(out.attack==167);
 sentinel=out;input.iv[0]=32;
 assert(!MegaForm_Calculate(MEGA_FORM_VENUSAUR_MEGA,&input,neutral,&out));
 assert(!memcmp(&out,&sentinel,sizeof(out)));
 MegaBattle_Reset(&state);assert(!MegaBattle_GetForm(&state,0,0));
 return 0;
}'''
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'constants').mkdir();(root/'platform').mkdir()
            (root/'global.h').write_text('#include <stdint.h>\n#include <stddef.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint8_t bool8;\n#define TRUE 1\n#define FALSE 0\n')
            for name in ('species.h','pokemon.h','abilities.h'):
                shutil.copy(ROOT/'include/constants'/name,root/'constants'/name)
            for name in ('mega_forms.h','mega_battle.h'):
                shutil.copy(ROOT/'include/platform'/name,root/'platform'/name)
            (root/'main.c').write_text(main)
            exe=root/'test'
            cmd=['cc','-std=c99','-Wall','-Wextra','-Werror','-I',str(root),str(ROOT/'src/platform/mega_forms.c'),str(ROOT/'src/platform/mega_battle.c'),str(root/'main.c'),'-o',str(exe)]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
