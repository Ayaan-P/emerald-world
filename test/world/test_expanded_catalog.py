"""Narrow RC4 donor import tests. No personal saves or running services."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DONOR = ROOT.parent / 'expansion-foundation/engines/expansion-native'
OUT = ROOT / 'build/rc4-expanded/generated'


class ExpandedCatalogTest(unittest.TestCase):
    def test_native_tables_and_acquisition_are_wired_without_save_growth(self):
        constants = (ROOT / 'include/constants/species.h').read_text()
        self.assertIn('#define SPECIES_GIMMIGHOUL_ROAMING 440',
                      (ROOT / 'include/constants/expanded_species.h').read_text())
        self.assertIn('#define NUM_SPECIES SPECIES_EGG', constants)
        self.assertIn('#define SPECIES_UNOWN_B (NUM_SPECIES + 1)', constants)
        self.assertIn('ExpandedSpecies_ResolveEncounter', (ROOT / 'src/wild_encounter.c').read_text())
        source = (ROOT / 'src/platform/expanded_species.c').read_text()
        self.assertIn('WorldRules_Enabled(WORLD_RULE_EXPANDED_ROSTER)', source)
        self.assertIn('MAP_GROUP(MAP_ROUTE101)', source)
        for table in ['species_info.h', 'level_up_learnset_pointers.h', 'tmhm_learnsets.h', 'tutor_learnsets.h']:
            self.assertIn('expanded/', (ROOT / 'src/data/pokemon' / table).read_text())
        for table in ['front_pic_table.h', 'still_front_pic_table.h', 'back_pic_table.h', 'palette_table.h', 'shiny_palette_table.h', 'front_pic_anims.h', 'footprint_table.h']:
            self.assertIn('expanded/', (ROOT / 'src/data/pokemon_graphics' / table).read_text())

    def test_compiled_native_tables_and_rule_gated_pool(self):
        build = ROOT / 'build/rc4-expanded/native'
        build.mkdir(parents=True, exist_ok=True)
        harness = build / 'catalog_core.c'
        harness.write_text(r'''
#include "global.h"
#include "pokemon.h"
#include "platform/expanded_species.h"
#include "platform/world_rules.h"
#include "constants/abilities.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "data/pokemon/species_info.h"
#include "data/pokemon/level_up_learnsets.h"
#include "data/pokemon/level_up_learnset_pointers.h"
#include "data/pokemon/evolution.h"
static u32 sRules;
bool8 WorldRules_Enabled(u32 rule) { return (sRules & rule) != 0; }
_Static_assert(sizeof(struct BoxPokemon) == 80, "Legacy box layout changed");
_Static_assert(sizeof(struct Pokemon) == 100, "Legacy party layout changed");
_Static_assert(SPECIES_EGG == 412 && SPECIES_UNOWN_B == 413 && SPECIES_UNOWN_QMARK == 439, "Legacy IDs moved");
_Static_assert(NUM_SPECIES == 412, "Legacy count grew");
int main(void)
{
    u16 mon = SPECIES_GIMMIGHOUL_ROAMING;
    if (ExpandedSpecies_ResolveEncounter(SPECIES_ZIGZAGOON, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) != SPECIES_ZIGZAGOON) return 1;
    sRules = WORLD_RULE_EXPANDED_ROSTER;
    if (ExpandedSpecies_ResolveEncounter(SPECIES_ZIGZAGOON, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) != mon) return 2;
    if (ExpandedSpecies_ResolveEncounter(SPECIES_ZIGZAGOON, MAP_GROUP(MAP_ROUTE102), MAP_NUM(MAP_ROUTE102)) != SPECIES_ZIGZAGOON) return 3;
    if (ExpandedSpecies_ResolveEncounter(SPECIES_WURMPLE, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) != SPECIES_MELTAN) return 4;
    if (gSpeciesInfo[mon].baseHP != 45 || gSpeciesInfo[mon].abilities[0] != ABILITY_RUN_AWAY) return 5;
    if (gLevelUpLearnsets[mon][0] != LEVEL_UP_MOVE(1, MOVE_ASTONISH) || gLevelUpLearnsets[mon][2] != LEVEL_UP_END) return 6;
    if (gSpeciesInfo[SPECIES_MELTAN].baseAttack != 65 || gSpeciesInfo[SPECIES_MELTAN].expYield != 150) return 7;
    if (gSpeciesInfo[SPECIES_COSMOEM].baseDefense != 131) return 8;
    if (ExpandedSpecies_NationalDexNumber(mon) != 999 || ExpandedSpecies_FromNationalDexNumber(808) != SPECIES_MELTAN) return 9;
    if (ExpandedSpecies_IsPlayable(441) || !ExpandedSpecies_IsPlayable(SPECIES_COSMOEM)) return 10;
    sRules = 0;
    if (!ExpandedSpecies_IsPlayable(mon) || !ExpandedSpecies_IsPlayable(SPECIES_MELTAN)) return 11;
    if (gEvolutionTable[mon][0].method != 0) return 12;
    puts("native tables, acquisition policy, stable IDs and 80/100-byte layouts passed");
    return 0;
}
''')
        exe = build / 'catalog_core'
        cmd = ['gcc', '-std=gnu11', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
               '-iquote', 'include', '-iquote', 'src', '-fno-builtin', '-Wall', '-Werror',
               str(harness), 'src/platform/expanded_species.c', '-o', str(exe)]
        subprocess.run(cmd, cwd=ROOT, check=True)
        result = subprocess.run([str(exe)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + f' native failure code {result.returncode}')
        self.assertIn('80/100-byte layouts passed', result.stdout)

    def test_native_tracer_preserves_donor_moves_and_legacy_ids(self):
        script = ROOT / 'tools/expanded/import_species.py'
        self.assertTrue(script.is_file(), 'native expanded import generator is missing')
        subprocess.run([sys.executable, str(script), '--donor', str(DONOR),
                        '--output', str(OUT)], check=True, cwd=ROOT)
        manifest = json.loads((OUT / 'tools/expanded/coverage.json').read_text())
        self.assertEqual(manifest['source_commit'], 'bb3fd057061cdd7e6a9e79b76abb41924ee44ecc')
        rows = {row['name']: row for row in manifest['species']}
        self.assertEqual(rows['SPECIES_TREECKO']['engine_id'], 277)
        self.assertEqual(rows['SPECIES_UNOWN_B']['engine_id'], 413)
        self.assertTrue({'SPECIES_GIMMIGHOUL_ROAMING', 'SPECIES_MELTAN', 'SPECIES_COSMOEM'}
                        <= set(manifest['playable_selection']))
        self.assertEqual(set(manifest['playable_selection']),
                         {r['name'] for r in rows.values() if r['status'] == 'native_selected'})
        for name in manifest['playable_selection']:
            self.assertEqual(rows[name]['missing_level_up_moves'], [])
            self.assertEqual(rows[name]['missing_normal_abilities'], [])
        self.assertEqual(rows['SPECIES_MELTAN']['engine_id'], 863)
        tracer = rows['SPECIES_GIMMIGHOUL_ROAMING']
        self.assertEqual(tracer['engine_id'], 440)
        self.assertEqual(tracer['level_up_moves'], [[1, 'MOVE_ASTONISH'], [1, 'MOVE_TACKLE']])
        self.assertEqual(tracer['missing_level_up_moves'], [])
        self.assertEqual(tracer['missing_abilities'], [])
        self.assertIn('evolution', tracer['unsupported_features'])
        self.assertIn('ITEM_GIMMIGHOUL_COIN', tracer['donor_species_source'])
        canonical = [r for r in rows.values() if not r.get('alias_of')]
        self.assertEqual(len({r['engine_id'] for r in canonical}), len(canonical))
        learnset = (OUT / 'src/data/pokemon/expanded/learnsets.inc').read_text()
        self.assertIn('LEVEL_UP_MOVE(1, MOVE_ASTONISH)', learnset)
        self.assertIn('LEVEL_UP_MOVE(1, MOVE_TACKLE)', learnset)
        self.assertTrue((OUT / 'graphics/expanded/gimmighoul_roaming/front.png').is_file())


if __name__ == '__main__':
    unittest.main()
