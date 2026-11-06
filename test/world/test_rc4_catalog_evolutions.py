"""Staged dependency-selected evolution import and native production seam."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from test.world.test_expanded_runtime import function

ROOT = Path(__file__).resolve().parents[2]
DONOR = ROOT.parent / 'expansion-foundation/engines/expansion-native'
STAGE = ROOT / 'build/rc4-catalog-evolutions'
OUT = STAGE / 'generated'


def importer():
    spec = importlib.util.spec_from_file_location('evolution_import', ROOT / 'tools/expanded/import_species.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CatalogEvolutionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / 'tools/expanded/import_species.py'),
                        '--donor', str(DONOR), '--output', str(OUT)], check=True, cwd=ROOT)
        cls.manifest = json.loads((OUT / 'tools/expanded/coverage.json').read_text())
        cls.rows = {r['name']: r for r in cls.manifest['species']}

    def test_parser_rejects_unproven_descriptors_without_substitutions(self):
        parse = importer().classify_evolutions
        mapping = {'SPECIES_TEST': 900, 'SPECIES_IVYSAUR': 2, 'SPECIES_RESERVED': 901}
        native = {'SPECIES_IVYSAUR'}
        selected = {'SPECIES_TEST'}
        def classify(body):
            return parse('.evolutions = EVOLUTION(' + body + '),', mapping, native, selected)
        for raw in ('{EVO_LEVEL, 018, SPECIES_TEST}',
                    '{EVO_LEVEL, 0, SPECIES_TEST}', '{EVO_LEVEL, 101, SPECIES_TEST}',
                    '{EVO_LEVEL, 1 + 15, SPECIES_TEST}',
                    '{EVO_LEVEL, SOME_LEVEL, SPECIES_TEST}',
                    '{EVO_TRADE, 16, SPECIES_TEST}',
                    '{EVO_LEVEL, 16, SPECIES_RESERVED}',
                    '{EVO_LEVEL, 16, SPECIES_TEST, CONDITIONS({IF_TIME, TIME_NIGHT})}',
                    '{EVO_LEVEL, 16, SPECIES_TEST}, UNKNOWN_MACRO'):
            with self.subTest(raw=raw):
                supported, unsupported = classify(raw)
                self.assertEqual(supported, [])
                self.assertTrue(unsupported)
                self.assertTrue(all(e['reasons'] for e in unsupported))
        for target in ('SPECIES_TEST', 'SPECIES_IVYSAUR'):
            supported, unsupported = classify('{EVO_LEVEL, 16, ' + target + '}')
            self.assertEqual(unsupported, [])
            self.assertEqual(supported[0]['target'], target)
        supported, unsupported = classify('{EVO_LEVEL, 16, SPECIES_TEST}, {EVO_LEVEL, 32, SPECIES_RESERVED}')
        self.assertEqual(len(supported), 1)
        self.assertEqual(unsupported[0]['target'], 'SPECIES_RESERVED')
        for source in ('.evolutions = UNKNOWN({EVO_LEVEL, 16, SPECIES_TEST}),',
                       '.evolutions = EVOLUTION({EVO_LEVEL, 16, SPECIES_TEST}',
                       '#if UNKNOWN\n.evolutions = EVOLUTION({EVO_LEVEL, 16, SPECIES_TEST}),\n#endif'):
            supported, unsupported = parse(source, mapping, native, selected)
            self.assertEqual(supported, [])
            self.assertTrue(unsupported)
        supported, unsupported = classify(', '.join(['{EVO_LEVEL, 16, SPECIES_TEST}'] * 6))
        self.assertEqual(supported, [])
        self.assertEqual(len(unsupported), 6)

    def test_actual_table_and_production_evolution_thresholds_rule_off_and_abi(self):
        # Mirror only the owned header, so its relative include resolves exclusively
        # against this staging tree, never shared generated data.
        table = STAGE / 'evolution.h'
        table.write_text((ROOT / 'src/data/pokemon/evolution.h').read_text())
        baseline = subprocess.check_output(['git', 'show', 'HEAD:src/data/pokemon/evolution.h'], cwd=ROOT, text=True)
        baseline = baseline.replace('gEvolutionTable', 'baselineEvolutionTable')
        source = '''#include "global.h"
#include "pokemon.h"
#include "constants/items.h"
#include "constants/hold_effects.h"
#include "siirtc.h"
#include "platform/expanded_species.h"
#include "platform/world_rules.h"
#include "constants/maps.h"
#undef NDEBUG
#include <assert.h>
#include <string.h>
'''
        source += '#include "' + str(table) + '"\n' + baseline + '\n'
        source += '_Static_assert(EVOS_PER_MON == 5, "importer evolution capacity");\n'
        source += '''static u16 testSpecies, testItem;
static u8 testLevel;
struct SaveBlock1 *gSaveBlock1Ptr;
struct Time gLocalTime;
static bool8 rules;
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return rules; }
u8 GetItemHoldEffect(u16 item) { return item == ITEM_EVERSTONE ? HOLD_EFFECT_PREVENT_EVOLVE : 0; }
void RtcCalcLocalTime(void) {}
u32 GetMonData(struct Pokemon *mon, s32 field, u8 *data) {
    (void)mon; (void)data;
    switch(field) {
    case MON_DATA_SPECIES: return testSpecies;
    case MON_DATA_HELD_ITEM: return testItem;
    case MON_DATA_LEVEL: return testLevel;
    default: return 0;
    }
}
void SetMonData(struct Pokemon *mon, s32 field, const void *value) {
    (void)mon; (void)field; (void)value; assert(0);
}
'''
        runtime = (ROOT / 'src/pokemon.c').read_text()
        import re
        source += '\n'.join(re.findall(r'^#define (?:DAY_EVO_\w+|NIGHT_EVO_\w+|FRIENDSHIP_EVO_THRESHOLD)\s+[^\n]+', runtime, re.M)) + '\n'
        source += function(runtime, 'GetEvolutionTargetSpecies') + '\n'
        source += '''int main(void) {
    struct Pokemon mon;
    memset(&mon, 0x5a, sizeof(mon));
    struct Pokemon before = mon;
    _Static_assert(sizeof(struct BoxPokemon) == 80, "box ABI");
    _Static_assert(sizeof(struct Pokemon) == 100, "party ABI");
    _Static_assert(NUM_SPECIES == 412, "legacy count");
    assert(memcmp(gEvolutionTable, baselineEvolutionTable, sizeof(baselineEvolutionTable)) == 0);
'''
        for name, level, target in [('TURTWIG', 18, 'GROTLE'), ('GROTLE', 32, 'TORTERRA'), ('CHESPIN', 16, 'QUILLADIN')]:
            source += f'''testSpecies = SPECIES_{name};
for (rules = 0; rules <= 1; rules++) {{
    assert(ExpandedSpecies_Clamp(testSpecies) == testSpecies);
    assert(ExpandedSpecies_ResolveEncounter(SPECIES_ZIGZAGOON, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) == (rules ? SPECIES_GIMMIGHOUL_ROAMING : SPECIES_ZIGZAGOON));
    testLevel = {level - 1}; assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, 0) == SPECIES_NONE);
    testLevel = {level}; assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, 0) == SPECIES_{target});
    testLevel = {level + 1}; assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, 0) == SPECIES_{target});
    testItem = ITEM_EVERSTONE; assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, 0) == SPECIES_NONE);
    testItem = ITEM_NONE;
    assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_TRADE, 0) == SPECIES_NONE);
    assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_ITEM_USE, ITEM_LEAF_STONE) == SPECIES_NONE);
    assert(memcmp(&mon, &before, sizeof(mon)) == 0);
}}
'''
        for name in ('TORTERRA', 'QUILLADIN', 'TYPE_NULL', 'COSMOEM', 'MELTAN', 'GIMMIGHOUL_ROAMING', 'ARROKUDA', 'KUBFU'):
            source += f'testSpecies = SPECIES_{name}; testLevel = 100; assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, 0) == SPECIES_NONE);\n'
        source += '''testSpecies = SPECIES_BULBASAUR; testLevel = 16;
assert(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, 0) == SPECIES_IVYSAUR);
puts("actual staged table + real GetEvolutionTargetSpecies: thresholds, rules off/on, Everstone, modes, identity, vanilla rows, 80/100-byte ABI PASS");
return 0;
}
'''
        harness, exe = STAGE / 'native_evolution.c', STAGE / 'native_evolution'
        harness.write_text(source)
        # Mirror the unchanged production adapter to stage so its generated
        # relative includes exercise the same coherent staged catalog.
        adapter = OUT / 'src/platform/expanded_species.c'
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text((ROOT / 'src/platform/expanded_species.c').read_text())
        import shutil
        compilers = ['gcc']
        if shutil.which('clang'):
            compilers.append('clang')
        else:
            print('clang UNVERIFIED: executable not installed; gcc production seam remains mandatory')
        for compiler in compilers:
            command = [compiler, '-std=gnu11', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
                       '-include', str(OUT / 'include/constants/expanded_species.h'),
                       '-iquote', str(OUT / 'src/data/pokemon'), '-iquote', str(OUT / 'include'),
                       '-iquote', str(ROOT / 'include'), '-iquote', str(ROOT / 'src'),
                       '-fno-builtin', '-Wall', '-Werror', str(harness), str(adapter), '-o', str(exe)]
            (STAGE / (compiler + '-command.json')).write_text(json.dumps(command, indent=2) + '\n')
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(compiler + ': ' + result.stdout.strip())

    def test_exact_selected_edges_and_explicit_incomplete_chains(self):
        self.assertTrue((OUT / 'src/data/pokemon/expanded/evolution.inc').is_file(),
                        'missing staged native evolution table')
        supported = {n: r['supported_evolutions'] for n, r in self.rows.items()
                     if r.get('supported_evolutions')}
        self.assertEqual(set(supported), {'SPECIES_TURTWIG', 'SPECIES_GROTLE', 'SPECIES_CHESPIN'})
        for name, level, target in [('TURTWIG', 18, 'GROTLE'), ('GROTLE', 32, 'TORTERRA'), ('CHESPIN', 16, 'QUILLADIN')]:
            row = self.rows['SPECIES_' + name]
            edge, = row['supported_evolutions']
            self.assertEqual((edge['method'], edge['param'], edge['target']),
                             ('EVO_LEVEL', level, 'SPECIES_' + target))
            self.assertEqual(edge['target_engine_id'], self.rows[edge['target']]['engine_id'])
            self.assertEqual(row['unsupported_evolutions'], [])
            self.assertNotIn('evolution', row['unsupported_features'])
            self.assertTrue(row['obtainable'])
            self.assertNotIn('acquisition_route', row['unsupported_features'])
        for name, target in [('QUILLADIN', 'CHESNAUGHT')]:
            row = self.rows['SPECIES_' + name]
            self.assertEqual(row['supported_evolutions'], [])
            edge = row['unsupported_evolutions'][0]
            self.assertEqual(edge['target'], 'SPECIES_' + target)
            self.assertEqual(edge['param'], 36)
            self.assertIn(edge['raw'], row['resolved_species_source'])
            self.assertIn('target_not_native_or_selected', row['unsupported_evolutions'][0]['reasons'])
            self.assertIn('evolution', row['unsupported_features'])
        for name in ('TYPE_NULL', 'COSMOEM', 'GIMMIGHOUL_ROAMING'):
            self.assertIn('evolution', self.rows['SPECIES_' + name]['unsupported_features'])
        baseline = json.loads((ROOT / 'tools/expanded/coverage.json').read_text())
        self.assertEqual(self.manifest['playable_selection'], baseline['playable_selection'])
        self.assertEqual(len(self.rows), 1670)
        self.assertEqual({n: r['engine_id'] for n, r in self.rows.items()},
                         {r['name']: r['engine_id'] for r in baseline['species']})
        self.assertEqual(len(self.manifest['playable_selection']), 11)
        self.assertEqual(len(self.manifest['obtainable_selection']), 10)


if __name__ == '__main__':
    unittest.main()
