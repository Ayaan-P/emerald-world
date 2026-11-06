"""Actual production C seams against candidate55; not native gameplay proof."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'test'))
from test_dexnav_lifecycle import function
STAGE = ROOT / 'build/rc4-self-drop-move-catalog/species-candidate55'
OUT = ROOT / 'build/rc4-arrokuda-native/c-seams'


class ArrokudaAcquisition(unittest.TestCase):
    def harness(self, mode='playable'):
        header = STAGE / 'include/constants/expanded_species.h'
        cases = (STAGE / 'src/data/pokemon/expanded/playable_cases.inc').read_text()
        if mode == 'not-playable':
            cases = re.sub(r'^.*case SPECIES_ARROKUDA:.*\n', '', cases, flags=re.M)
        elif mode == 'macro-absent':
            OUT.mkdir(parents=True, exist_ok=True)
            text = re.sub(r'^#define SPECIES_ARROKUDA .*\n', '', header.read_text(), flags=re.M)
            header = OUT / 'expanded-without-arrokuda.h'
            header.write_text(text)
            cases = re.sub(r'^.*case SPECIES_ARROKUDA:.*\n', '', cases, flags=re.M)
        src = (ROOT / 'src/platform/expanded_species.c').read_text()
        policy = function(src, 'ExpandedSpecies_IsPlayable').replace('#include "../data/pokemon/expanded/playable_cases.inc"', cases)
        policy += '\n' + function(src, 'ExpandedSpecies_ResolveEncounter')
        wild = (ROOT / 'src/wild_encounter.c').read_text()
        prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
HEADER
#include "constants/species.h"
#include "constants/maps.h"
typedef uint8_t u8;typedef uint16_t u16;typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define WORLD_RULE_EXPANDED_ROSTER 16
static int enabled,draws,roll;
static int WorldRules_Enabled(int rule){assert(rule==16);return enabled;}
static u16 Random(void){draws++;return roll;}
static struct {struct {u8 mapGroup,mapNum;} location;} save,*gSaveBlock1Ptr=&save;
static u16 finalSpecies;static u8 finalLevel;
static void CreateWildMonExact(u16 s,u8 l){finalSpecies=s;finalLevel=l;}
'''.replace('HEADER', '#include "'+str(header)+'"')
        return prefix + policy + '\n' + function(wild, 'CreateWildMon')

    def run_c(self, name, code):
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / name
        path.with_suffix('.c').write_text(code)
        build = subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-iquote',str(ROOT/'include'),str(path.with_suffix('.c')),'-o',str(path)], capture_output=True, text=True)
        self.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(path)], capture_output=True, text=True)
        path.with_suffix('.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)

    def test_playable_extra_and_original_retained(self):
        rows = json.loads((STAGE/'tools/expanded/coverage.json').read_text())['species']
        row = next(r for r in rows if r['name']=='SPECIES_ARROKUDA')
        self.assertEqual(row['import_blockers'], [])
        self.assertTrue(row['battle_supported'])
        header = (STAGE/'include/constants/expanded_species.h').read_text()
        target = int(re.search(r'^#define SPECIES_ARROKUDA (\d+)$', header, re.M)[1])
        self.assertEqual(row['engine_id'], target)
        self.run_c('playable', self.harness()+r'''
int main(void){
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE103);save.location.mapNum=MAP_NUM(MAP_ROUTE103);
 enabled=1;assert(ExpandedSpecies_IsPlayable(SPECIES_ARROKUDA));
 assert(ExpandedSpecies_ResolveEncounter(SPECIES_MAGIKARP,save.location.mapGroup,save.location.mapNum)==SPECIES_ARROKUDA);
 assert(draws==0);
 roll=0;CreateWildMon(SPECIES_MAGIKARP,7);assert(finalSpecies==SPECIES_MAGIKARP && finalLevel==7 && draws==1);
 roll=1;CreateWildMon(SPECIES_MAGIKARP,9);assert(finalSpecies==SPECIES_ARROKUDA && finalLevel==9 && draws==2);
 puts("PASS production resolver + ordinary wrapper: pure lookup, original/extra, level preserved");
}
''')

    def test_rule_off_unrelated_map_and_source_no_extra_rng(self):
        self.run_c('unchanged', self.harness()+r'''
int main(void){
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE103);save.location.mapNum=MAP_NUM(MAP_ROUTE103);roll=1;
 enabled=0;CreateWildMon(SPECIES_MAGIKARP,5);assert(finalSpecies==SPECIES_MAGIKARP && draws==0);
 enabled=1;save.location.mapNum=MAP_NUM(MAP_ROUTE102);
 CreateWildMon(SPECIES_MAGIKARP,6);assert(finalSpecies==SPECIES_MAGIKARP && draws==0);
 save.location.mapNum=MAP_NUM(MAP_ROUTE103);save.location.mapGroup++;
 CreateWildMon(SPECIES_MAGIKARP,6);assert(finalSpecies==SPECIES_MAGIKARP && draws==0);
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE103);
 CreateWildMon(SPECIES_TENTACOOL,8);assert(finalSpecies==SPECIES_TENTACOOL && draws==0);
 puts("PASS off/map/group/source unchanged; zero overlay RNG");
}
''')

    def test_not_playable_and_absent_macro_no_extra_rng(self):
        for mode in ['not-playable','macro-absent']:
            self.run_c(mode, self.harness(mode)+r'''
int main(void){enabled=1;roll=1;
 save.location.mapGroup=MAP_GROUP(MAP_ROUTE103);save.location.mapNum=MAP_NUM(MAP_ROUTE103);
 CreateWildMon(SPECIES_MAGIKARP,10);assert(finalSpecies==SPECIES_MAGIKARP && finalLevel==10 && draws==0);
 puts("PASS unpromoted target leaves source and RNG intact");}
''')

    def test_real_old_rod_header_and_fishing_call_chain(self):
        src = (ROOT/'src/data/wild_encounters.h').read_text()
        slots = re.search(r'gRoute103_FishingMons\[\]\s*=\s*\{(.*?)\};',src,re.S)[1]
        first = re.findall(r'\{\s*(\d+),\s*(\d+),\s*(SPECIES_\w+)\s*\}',slots)[0]
        self.assertEqual(first, ('5','10','SPECIES_MAGIKARP'))
        self.assertIn('.fishingMonsInfo = &gRoute103_FishingMonsInfo',src)
        wild = (ROOT/'src/wild_encounter.c').read_text()
        self.assertIn('GenerateFishingWildMon(',function(wild,'FishingWildEncounter'))
        self.assertIn('CreateWildMon(',function(wild,'GenerateFishingWildMon'))
        self.assertNotIn('CreateWildMonExact(',function(wild,'GenerateFishingWildMon'))
        choose = function(wild,'ChooseWildMonIndex_Fishing')
        self.assertRegex(choose,r'case OLD_ROD:.*?wildMonIndex = 0;' .replace('.*?',r'[\s\S]*?'))


if __name__ == '__main__':
    unittest.main()
