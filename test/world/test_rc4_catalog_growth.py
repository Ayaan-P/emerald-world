"""Dependency-closed catalog growth, with disposable generated output only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DONOR = ROOT.parent / 'expansion-foundation/engines/expansion-native'
OUT = ROOT / 'build/rc4-acquisition-coverage/test-current/generated'


class CatalogGrowthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / 'tools/expanded/import_species.py'),
                        '--donor', str(DONOR), '--output', str(OUT)], check=True, cwd=ROOT)
        cls.manifest = json.loads((OUT / 'tools/expanded/coverage.json').read_text())
        cls.rows = {r['name']: r for r in cls.manifest['species']}

    def test_native_normal_variant_keeps_unsupported_hidden_metadata(self):
        row = self.rows['SPECIES_CHESPIN']
        self.assertIn(row['name'], self.manifest['playable_selection'])
        self.assertEqual(row['supported_slots'], [0, 1])
        self.assertEqual(row['normal_abilities'], ['ABILITY_OVERGROW', 'ABILITY_NONE'])
        self.assertEqual(row['hidden_ability'], 'ABILITY_BULLETPROOF')
        self.assertFalse(row['hidden_ability_supported'])
        self.assertIn('hidden_ability_slot', row['unsupported_features'])
        self.assertEqual(row['missing_normal_abilities'], [])
        self.assertEqual(row['missing_abilities'], ['ABILITY_BULLETPROOF'])
        self.assertTrue(row['obtainable'])
        control = self.rows['SPECIES_SIMISAGE']
        self.assertFalse(control['battle_supported'])
        self.assertIn('ABILITY_GLUTTONY', control['missing_normal_abilities'])
        self.assertIn('unsupported_abilities', control['import_blockers'])

    def test_gen9_evaluator_resolves_only_proven_direct_conditions(self):
        spec = importlib.util.spec_from_file_location('catalog_import', ROOT / 'tools/expanded/import_species.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        resolve = getattr(module, 'resolve_gen9', None)
        self.assertTrue(callable(resolve), 'requires a conservative Gen9 evaluator')
        assert callable(resolve)
        for expr in ('1 + (P_UPDATED_STATS >= GEN_7) ? 61 : 1',
                     '(P_UPDATED_STATS >= GEN_7) ? 61 : 1 + 2',
                     'MACRO((P_UPDATED_STATS >= GEN_7) ? 61 : 1)'):
            self.assertEqual(resolve(expr), expr)
        declaration = '''#if P_UPDATED_STATS >= GEN_10
.baseAttack = 1,
#elif P_UPDATED_STATS >= GEN_7
.baseAttack = (P_UPDATED_STATS >= GEN_10) ? 2 : 68,
#else
.baseAttack = 3,
#endif
'''
        self.assertEqual(resolve(declaration), '.baseAttack = 68,\n')
        unknown = '#if P_UNKNOWN >= GEN_7\n.abilities = { ABILITY_NONE },\n#endif\n'
        self.assertEqual(resolve(unknown), unknown)
        composition = '#if P_UPDATED_STATS >= GEN_7 && P_UNKNOWN\nX\n#else\nY\n#endif\n'
        self.assertEqual(resolve(composition), composition)
        self.assertEqual(resolve('P_UPDATED_STATS >= GEN_7 ? OTHER_MACRO : 2'),
                         'P_UPDATED_STATS >= GEN_7 ? OTHER_MACRO : 2')
        self.assertEqual(resolve('#if P_UPDATED_STATS >= GEN_7\nX\n'),
                         '#if P_UPDATED_STATS >= GEN_7\nX\n')

    def test_unknown_normal_slot_and_stat_composition_fail_closed(self):
        spec = importlib.util.spec_from_file_location('catalog_import', ROOT / 'tools/expanded/import_species.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        row = dict(self.rows['SPECIES_CHESPIN'])
        row['resolved_species_source'] = row['resolved_species_source'].replace(
            'ABILITY_OVERGROW, ABILITY_NONE, ABILITY_BULLETPROOF',
            'ABILITY_OVERGROW, UNKNOWN_SLOT, ABILITY_BULLETPROOF')
        self.assertIn('unresolved_ability_slots', module.import_blockers(row, DONOR, set()))
        row = dict(self.rows['SPECIES_CHESPIN'])
        import re
        row['resolved_species_source'] = re.sub(r'(\.baseAttack\s*=\s*)\d+',
            r'\g<1>(P_UNKNOWN >= GEN_7) ? 61 : 1', row['resolved_species_source'])
        self.assertIn('unresolved_serialized_field:baseAttack', module.import_blockers(row, DONOR, set()))

    def test_dependency_complete_growth_preserves_every_assigned_id(self):
        self.assertIn('SPECIES_TYPE_NULL', self.manifest['playable_selection'])
        self.assertEqual(len(self.rows), 1670)
        baseline = json.loads((ROOT / 'tools/expanded/coverage.json').read_text())
        self.assertEqual({r['name']: r['engine_id'] for r in baseline['species']},
                         {n: r['engine_id'] for n, r in self.rows.items()})
        self.assertEqual(self.rows['SPECIES_TYPE_NULL']['engine_id'], 827)
        self.assertEqual(self.rows['SPECIES_TREECKO']['engine_id'], 277)
        self.assertEqual(self.rows['SPECIES_UNOWN_B']['engine_id'], 413)


    def test_symbol_mentions_do_not_count_as_supported_dependencies(self):
        spec = importlib.util.spec_from_file_location('catalog_import', ROOT / 'tools/expanded/import_species.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, 'defined_symbols', None)), 'dependency parser must distinguish definitions from mentions')
        self.assertEqual(module.defined_symbols('#define MOVE_TACKLE 33\n// MOVE_INVENTED\n', 'MOVE_'),
                         {'MOVE_TACKLE'})

    def test_unresolved_ability_slots_are_not_treated_as_dependency_free(self):
        spec = importlib.util.spec_from_file_location('catalog_import', ROOT / 'tools/expanded/import_species.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        row = dict(self.rows['SPECIES_TYPE_NULL'])
        row['normal_abilities'] = []
        self.assertIn('unresolved_ability_slots', module.import_blockers(row, DONOR, set()))

    def test_staged_native_tables_compile_and_preserve_donor_battle_data(self):
        generated = OUT / 'src/data/pokemon/expanded'
        source = '''#include "global.h"
#include "pokemon.h"
#include "sprite.h"
#include "constants/abilities.h"
#include "constants/items.h"
#include "constants/moves.h"
#undef NDEBUG
#include <assert.h>
#define LEVEL_UP_MOVE(lvl, move) ((lvl << 9) | move)
#define PERCENT_FEMALE(percent) min(254, ((percent * 255) / 100))
'''
        source += '#include "' + str(OUT / 'include/constants/expanded_species.h') + '"\n'
        source += 'static const struct SpeciesInfo stats[SPECIES_TABLE_COUNT] = {\n#include "' + str(generated / 'species_info.inc') + '"\n};\n'
        source += '#include "' + str(generated / 'learnsets.inc') + '"\n'
        source += 'static const u16 *const learns[SPECIES_TABLE_COUNT] = {\n#include "' + str(generated / 'learnset_pointers.inc') + '"\n};\n'
        source += '#include "' + str(generated / 'animations.inc') + '"\n'
        source += 'static const union AnimCmd *const *const animations[SPECIES_TABLE_COUNT] = {\n#include "' + str(generated / 'animation_pointers.inc') + '"\n};\n'
        from test.world.test_expanded_runtime import function
        runtime = (ROOT / 'src/pokemon.c').read_text()
        creator = function(runtime, 'CreateBoxMon')
        start = creator.index('    if (gSpeciesInfo[species].abilities[1])')
        end = creator.index('\n\n    GiveBoxMonInitialMoveset', start)
        source += '''#define gSpeciesInfo stats
static u32 selectedSlot;
u8 gLastUsedAbility;
u16 ExpandedSpecies_Clamp(u16 species) { return species; }
void SetBoxMonData(struct BoxPokemon *box, s32 field, const void *value) {
    (void)box; assert(field == MON_DATA_ABILITY_NUM); selectedSlot = *(const u32 *)value;
}
static u32 SelectOrdinarySlot(u16 species, u32 personality) {
    struct BoxPokemon *boxMon = NULL;
    u32 value = 0;
    selectedSlot = 0;
'''
        source += creator[start:end] + '\nreturn selectedSlot;\n}\n'
        source += function(runtime, 'GetAbilityBySpecies') + '\n'
        source += '''int main(void) {
_Static_assert(sizeof(struct BoxPokemon) == 80, "box ABI");
_Static_assert(sizeof(struct Pokemon) == 100, "party ABI");
_Static_assert(NUM_SPECIES == 412 && SPECIES_UNOWN_QMARK == 439, "legacy IDs");
assert(stats[SPECIES_TYPE_NULL].baseHP == 95);
assert(stats[SPECIES_TYPE_NULL].abilities[0] == ABILITY_BATTLE_ARMOR);
assert(stats[SPECIES_TYPE_NULL].abilities[1] == ABILITY_NONE);
'''
        for name in self.manifest['playable_selection']:
            for slot, ability in enumerate(self.rows[name]['normal_abilities']):
                source += f'assert(stats[{name}].abilities[{slot}] == {ability});\n'
                source += f'assert(GetAbilityBySpecies({name}, {slot}) == {ability});\n'
            for personality in (0, 1):
                slot = personality if self.rows[name]['normal_abilities'][1] != 'ABILITY_NONE' else 0
                ability = self.rows[name]['normal_abilities'][slot]
                source += f'assert(SelectOrdinarySlot({name}, {personality}) == {slot});\n'
                source += f'assert(GetAbilityBySpecies({name}, selectedSlot) == {ability});\n'
            for index, (level, move) in enumerate(self.rows[name]['level_up_moves']):
                source += f'assert(learns[{name}][{index}] == LEVEL_UP_MOVE({level}, {move}));\n'
            length = len(self.rows[name]['level_up_moves'])
            source += f'assert(learns[{name}][{length}] == LEVEL_UP_END);\n'
            source += f'assert(animations[{name}][0][0].frame.imageValue == 0);\nassert(animations[{name}][1][0].frame.imageValue == 0);\n'
        source += 'puts("staged normal-variant stats, native ability selection, exact learnsets, animations and save ABI passed"); return 0; }\n'
        harness = OUT.parent / 'catalog_growth.c'
        harness.write_text(source)
        exe = OUT.parent / 'catalog_growth'
        result = subprocess.run(['gcc', '-std=gnu11', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
                                 '-include', str(OUT / 'include/constants/expanded_species.h'),
                                 '-iquote', 'include', '-iquote', 'src', '-fno-builtin', '-Wall', '-Werror',
                                 str(harness), '-o', str(exe)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(exe)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_staged_assets_have_exact_provenance_and_native_dimensions(self):
        import hashlib
        from PIL import Image
        assets = json.loads((OUT / 'tools/expanded/assets.json').read_text())['assets']
        self.assertEqual(len(assets), 6 * len(self.manifest['playable_selection']))
        for asset in assets:
            path = OUT / asset['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), asset['sha256'])
            self.assertEqual(hashlib.sha256((DONOR / asset['donor_path']).read_bytes()).hexdigest(), asset['source_sha256'])
            if path.name in ('front.png', 'back.png'):
                with Image.open(path) as image:
                    self.assertEqual(image.size, (64, 64))

    def test_support_and_acquisition_are_distinct_and_fail_closed(self):
        # Selection stays dependency-driven as native move coverage grows.
        selected = {name for name, row in self.rows.items()
                    if row['engine_id'] >= 440 and not row['import_blockers']}
        self.assertEqual(set(self.manifest['playable_selection']), selected)
        self.assertEqual(self.manifest['obtainable_selection'][:6], [
            'SPECIES_GIMMIGHOUL_ROAMING', 'SPECIES_MELTAN', 'SPECIES_COSMOEM',
            'SPECIES_TYPE_NULL', 'SPECIES_TURTWIG', 'SPECIES_CHESPIN'])
        self.assertTrue({'SPECIES_GROTLE', 'SPECIES_QUILLADIN'} <=
                        set(self.manifest['obtainable_selection']))
        for row in self.rows.values():
            if row['status'] == 'reserved_not_playable':
                self.assertFalse(row['battle_supported'])
                self.assertFalse(row['obtainable'])
                self.assertTrue(row['import_blockers'])
        grown = self.rows['SPECIES_TYPE_NULL']
        self.assertTrue(grown['battle_supported'])
        self.assertTrue(grown['obtainable'])
        self.assertNotIn('acquisition_route', grown['unsupported_features'])
        self.assertIn('evolution', grown['unsupported_features'])
        self.assertIn('cry_audio', grown['unsupported_features'])
        self.assertIn('unsupported_abilities', self.rows['SPECIES_COSMOG']['import_blockers'])
        self.assertTrue(self.rows['SPECIES_TURTWIG']['battle_supported'])
        self.assertIn('hidden_ability_slot', self.rows['SPECIES_TURTWIG']['unsupported_features'])
        self.assertIn('unresolved_species_fields', self.rows['SPECIES_ARCEUS_NORMAL']['import_blockers'])
        self.assertIn('modern_split', self.manifest['battle_support_requires'])
        self.assertEqual(grown['hidden_ability'], 'ABILITY_NONE')


if __name__ == '__main__':
    unittest.main()
