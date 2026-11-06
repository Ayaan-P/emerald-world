"""Disposable move catalog growth. Never promote generated output in tests."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DONOR = ROOT.parent / 'expansion-foundation/engines/expansion-native'
OUT = ROOT / 'build/rc4-self-drop-move-catalog/generated'


class MoveCatalogGrowthTests(unittest.TestCase):
    def test_staged_output_preserves_legacy_bytes_and_is_deterministic(self):
        import hashlib
        paths = ['include/constants/moves.h', 'data/expanded_move_animations.inc',
                 'tools/expanded_moves/coverage.json', 'src/data/battle_moves.h',
                 'src/data/contest_moves.h', 'src/data/text/move_names.h',
                 'src/data/text/move_descriptions.h', 'data/battle_anim_scripts.s']
        paths += [str(p.relative_to(ROOT)) for p in (ROOT / 'src/data/expanded_moves').glob('*.h')]
        before = {p: (ROOT / p).read_bytes() for p in paths}
        command = [sys.executable, str(ROOT / 'tools/expanded_moves/generate.py'),
                   '--donor', str(DONOR), '--output', str(OUT)]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        coverage = json.loads((OUT / 'tools/expanded_moves/coverage.json').read_text())
        old = json.loads(before['tools/expanded_moves/coverage.json'])
        self.assertEqual(coverage['effect_supported'][:len(old['effect_supported'])], old['effect_supported'])
        import re
        definitions = lambda b: dict(re.findall(rb'^#define (MOVE_\w+) ([^\n]+)$', b, re.M))
        ids = definitions((OUT / 'include/constants/moves.h').read_bytes())
        for name, value in definitions(before['include/constants/moves.h']).items():
            self.assertEqual(ids[name], value)
        self.assertLessEqual(coverage['move_count'], 512)
        for path in paths:
            self.assertEqual((ROOT / path).read_bytes(), before[path], path)
            if path.startswith('src/data/') or path.endswith('.inc'):
                self.assertTrue((OUT / path).read_bytes().startswith(before[path]), path)
        digest = lambda: {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in OUT.rglob('*') if p.is_file()}
        first = digest()
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
        self.assertEqual(first, digest())

    def test_native_c_data_animation_indices_and_donor_properties(self):
        import re
        subprocess.run([sys.executable, str(ROOT / 'tools/expanded_moves/generate.py'),
                        '--donor', str(DONOR), '--output', str(OUT)], check=True, capture_output=True)
        coverage = json.loads((OUT / 'tools/expanded_moves/coverage.json').read_text())
        old = json.loads((ROOT / 'tools/expanded_moves/coverage.json').read_text())
        # Promotion puts the growth batch in the seed. Keep checking all twelve
        # donor bodies rather than accidentally running an empty assertion loop.
        added = [row for row in coverage['effect_supported'] if row['native_id'] >= 398]
        self.assertEqual(len(added), 12)
        self.assertIn('candidate_audit', coverage)
        donor = dict(re.findall(r'\[(MOVE_\w+)\] =\s*\{(.*?)\n    \},',
                                (DONOR / 'src/data/moves_info.h').read_text(), re.S))
        value = lambda body, key: re.search(r'^\s*\.'+key+r' = ([^,\n]+)', body, re.M)[1]
        source = '#include "global.h"\n#include "pokemon.h"\n#include "constants/battle_move_effects.h"\n#include "platform/expanded_moves.h"\n#undef NDEBUG\n#include <assert.h>\n'
        source += '\n'.join(line for line in (ROOT / 'include/battle.h').read_text().splitlines() if line.startswith('#define MOVE_TARGET')) + '\n'
        source += '#include "' + str(OUT / 'src/data/battle_moves.h') + '"\n'
        source += '#undef _\n#define _(x) x\n'
        source += '#include "' + str(OUT / 'src/data/text/move_names.h') + '"\n'
        source += '#include "' + str(OUT / 'src/data/text/move_descriptions.h') + '"\n'
        source += 'static const unsigned categories[] = {\n#include "' + str(OUT / 'src/data/expanded_moves/categories.h') + '"\n};\n'
        anim_source = (OUT / 'data/battle_anim_scripts.s').read_text().split('gBattleAnims_Moves::')[1]
        native_anim = re.findall(r'ptrvalue (Move_\w+)', anim_source.split('Move_PSYCHO_BOOST')[0]) + ['Move_PSYCHO_BOOST']
        expanded_anim = re.findall(r'ptrvalue (Move_\w+)', (OUT / 'data/expanded_move_animations.inc').read_text())
        self.assertEqual(len(native_anim), 355)
        self.assertEqual(len(expanded_anim), coverage['move_count']-355)
        labels = (ROOT / 'data/battle_anim_scripts.s').read_text()
        for label in expanded_anim:
            self.assertIn(label+':', labels)
        all_anim = native_anim + expanded_anim
        symbols = sorted(set(all_anim))
        source += 'enum { '+', '.join(symbols)+' };\n'
        source += 'static const int animation_indices[] = {'+', '.join(all_anim)+'};\nint main(void) {\n'
        source += f'assert(MOVES_COUNT == {coverage["move_count"]});\nassert(sizeof(gBattleMoves)/sizeof(gBattleMoves[0]) == MOVES_COUNT);\nassert(sizeof(animation_indices)/sizeof(animation_indices[0]) == MOVES_COUNT);\n'
        expected = {
            'MOVE_STONE_EDGE': ('EFFECT_HIGH_CRITICAL', 0),
            'MOVE_LIQUIDATION': ('EFFECT_DEFENSE_DOWN_HIT', 20),
            'MOVE_LUNGE': ('EFFECT_ATTACK_DOWN_HIT', 100),
            'MOVE_SKITTER_SMACK': ('EFFECT_SPECIAL_ATTACK_DOWN_HIT', 100),
            'MOVE_MYSTICAL_FIRE': ('EFFECT_SPECIAL_ATTACK_DOWN_HIT', 100),
            'MOVE_HIGH_HORSEPOWER': ('EFFECT_HIT', 0),
            'MOVE_WILD_CHARGE': ('EFFECT_RECOIL', 0),
            'MOVE_ACCELEROCK': ('EFFECT_HIT', 0),
            'MOVE_CLOSE_COMBAT': ('EFFECT_DEF_SPDEF_DOWN_HIT', 0),
            'MOVE_HEADLONG_RUSH': ('EFFECT_DEF_SPDEF_DOWN_HIT', 0),
            'MOVE_HAMMER_ARM': ('EFFECT_SELF_SPEED_DOWN_HIT', 0),
            'MOVE_ICE_HAMMER': ('EFFECT_SELF_SPEED_DOWN_HIT', 0),
        }
        for row in added:
            self.assertEqual((row['effect'], row['secondary_chance']), expected[row['name']])
            name = row['name']; body = donor[name]
            if name == 'MOVE_STONE_EDGE':
                self.assertEqual(value(body, 'criticalHitStage'), 'B_UPDATED_MOVE_DATA >= GEN_3 ? 1 : 2')
            if name == 'MOVE_WILD_CHARGE':
                self.assertIn('.recoilPercentage = 25', body)
                source += 'assert(gBattleMoves[MOVE_WILD_CHARGE].effect == gBattleMoves[MOVE_TAKE_DOWN].effect);\n'
            stat = {'MOVE_LIQUIDATION': 'defense', 'MOVE_LUNGE': 'attack',
                    'MOVE_SKITTER_SMACK': 'spAtk', 'MOVE_MYSTICAL_FIRE': 'spAtk'}.get(name)
            if stat:
                self.assertEqual(value(body, 'moveEffect'), 'MOVE_EFFECT_STAT_MINUS')
                self.assertEqual(value(body, stat), '1')
            for key in ['power', 'type', 'accuracy', 'pp', 'priority', 'target']:
                val = value(body, key)
                if name == 'MOVE_HEADLONG_RUSH' and key == 'power':
                    self.assertEqual(val, 'B_UPDATED_MOVE_DATA >= GEN_9 ? 120 : 100')
                    val = '120'
                if name == 'MOVE_MYSTICAL_FIRE' and key == 'power':
                    self.assertEqual(val, 'B_UPDATED_MOVE_DATA >= GEN_7 ? 75 : 65')
                    val = '75'
                val = val.replace('TARGET_', 'MOVE_TARGET_')
                source += f'assert(gBattleMoves[{name}].{key} == {val});\n'
            expected_chance = re.search(r'\.chance = (\d+)', body)
            chance = int(expected_chance[1]) if expected_chance else 0
            self.assertEqual(chance, row['secondary_chance'])
            flags = ['FLAG_PROTECT_AFFECTED', 'FLAG_MIRROR_MOVE_AFFECTED']
            if '.makesContact = TRUE' in body: flags.append('FLAG_MAKES_CONTACT')
            if not chance: flags.append('FLAG_KINGS_ROCK_AFFECTED')
            source += f'assert(gBattleMoves[{name}].flags == ({" | ".join(flags)}));\n'
            source += f'assert(gBattleMoves[{name}].effect == {row["effect"]});\nassert(gBattleMoves[{name}].secondaryEffectChance == {chance});\n'
            source += f'assert(categories[{name}-355] == {value(body, "category").replace("DAMAGE_CATEGORY_", "EXPANDED_CATEGORY_")});\n'
            source += f'assert(animation_indices[{name}] == {row["animation_reuse"]});\n'
            source += f'assert(gMoveNames[{name}][0]);\nassert(gMoveDescriptionPointers[{name}-1][0]);\n'
            self.assertNotRegex(body, r'\.(soundMove|thawsUser|ignoresProtect|mirrorMoveBanned|metronomeBanned) = TRUE')
        source += 'return 0; }\n'
        harness = OUT.parent / 'move_catalog_growth.c'; harness.write_text(source)
        exe = OUT.parent / 'move_catalog_growth'
        built = subprocess.run(['cc', '-std=gnu11', '-DPORTABLE', '-DVER_64BIT',
                                '-include', str(OUT / 'include/constants/moves.h'),
                                '-iquote', 'include', '-iquote', '.', '-Wall', '-Werror', str(harness), '-o', str(exe)],
                               cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], text=True, capture_output=True)
        self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_reordering_ports_cannot_renumber_any_assigned_id(self):
        import hashlib
        import re
        subprocess.run([sys.executable, str(ROOT / 'tools/expanded_moves/generate.py'),
                        '--donor', str(DONOR), '--output', str(OUT)], check=True, capture_output=True)
        reordered = OUT.parent / 'reordered'
        script = ('import runpy,sys; '
                  'm=runpy.run_path(sys.argv[1]); '
                  'm["PORTS"].reverse(); '
                  'sys.argv=[sys.argv[1],"--donor",sys.argv[2],"--output",sys.argv[3]]; '
                  'm["main"]()')
        ran = subprocess.run([sys.executable, '-c', script,
                              str(ROOT / 'tools/expanded_moves/generate.py'), str(DONOR), str(reordered)],
                             cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        baseline = json.loads((ROOT / 'tools/expanded_moves/coverage.json').read_text())['effect_supported']
        actual = json.loads((reordered / 'tools/expanded_moves/coverage.json').read_text())['effect_supported']
        self.assertEqual(actual[:len(baseline)], baseline)
        self.assertEqual(len(actual), 55)
        expected_ids = {r['name']: r['native_id'] for r in baseline}
        expected_ids.update({
            'MOVE_STONE_EDGE': 398, 'MOVE_LIQUIDATION': 399, 'MOVE_LUNGE': 400,
            'MOVE_SKITTER_SMACK': 401, 'MOVE_MYSTICAL_FIRE': 402,
            'MOVE_HIGH_HORSEPOWER': 403, 'MOVE_WILD_CHARGE': 404, 'MOVE_ACCELEROCK': 405,
            'MOVE_CLOSE_COMBAT': 406, 'MOVE_HEADLONG_RUSH': 407,
            'MOVE_HAMMER_ARM': 408, 'MOVE_ICE_HAMMER': 409,
        })
        self.assertEqual({r['name']: r['native_id'] for r in actual}, expected_ids)
        normal = json.loads((OUT / 'tools/expanded_moves/coverage.json').read_text())['effect_supported']
        self.assertEqual({r['name']: r['native_id'] for r in normal}, expected_ids)
        self.assertEqual(actual, normal)
        for stage in (OUT, reordered):
            constants = dict(re.findall(r'^#define (MOVE_\w+) (\d+)$',
                                       (stage / 'include/constants/moves.h').read_text(), re.M))
            self.assertEqual({name: int(constants[name]) for name in expected_ids}, expected_ids)
        digest = lambda stage: {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in stage.rglob('*') if p.is_file()}
        self.assertEqual(digest(OUT), digest(reordered))

    def test_invalid_stable_assignments_fail_before_staging_writes(self):
        cases = {
            'collision': 'm["ASSIGNED_IDS"]["MOVE_ACCELEROCK"]=404',
            'gap': 'm["ASSIGNED_IDS"]["MOVE_ACCELEROCK"]=406',
            'missing': 'm["PORTS"].append(("FIXTURE_UNASSIGNED", "HIT", 0, "TACKLE"))',
            'seed_conflict': 'm["ASSIGNED_IDS"]["MOVE_MOONBLAST"]=356',
        }
        for name, mutation in cases.items():
            with self.subTest(name=name):
                output = OUT.parent / ('invalid_' + name)
                script = ('import runpy,sys; m=runpy.run_path(sys.argv[1]); ' + mutation + '; '
                          'sys.argv=[sys.argv[1],"--donor",sys.argv[2],"--output",sys.argv[3]]; '
                          'm["main"]()')
                ran = subprocess.run([sys.executable, '-c', script,
                                      str(ROOT / 'tools/expanded_moves/generate.py'), str(DONOR), str(output)],
                                     cwd=ROOT, text=True, capture_output=True)
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn('ValueError:', ran.stderr)
                self.assertIn({'collision': 'disagree with legacy seed', 'gap': 'disagree with legacy seed',
                               'missing': 'Ports and stable assignments disagree',
                               'seed_conflict': 'disagree with legacy seed'}[name], ran.stderr)
                self.assertFalse(output.exists())

    def test_exact_new_batch(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('move_generator', ROOT / 'tools/expanded_moves/generate.py')
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old = json.loads((ROOT / 'tools/expanded_moves/coverage.json').read_text())
        installed_batch = {r['name'][5:] for r in old['effect_supported'] if r['native_id'] >= 398}
        added = {p[0] for p in module.PORTS} & installed_batch
        self.assertEqual(len(old['effect_supported']), 55)
        self.assertEqual(added, {'STONE_EDGE', 'LIQUIDATION', 'LUNGE', 'SKITTER_SMACK',
                                 'MYSTICAL_FIRE', 'HIGH_HORSEPOWER', 'WILD_CHARGE', 'ACCELEROCK',
                                 'CLOSE_COMBAT', 'HEADLONG_RUSH', 'HAMMER_ARM', 'ICE_HAMMER'})

    def test_stone_edge_has_native_high_critical_effect(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('move_generator', ROOT / 'tools/expanded_moves/generate.py')
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        self.assertIn(('STONE_EDGE', 'HIGH_CRITICAL', 0, 'ROCK_SLIDE'), module.PORTS)


if __name__ == '__main__':
    unittest.main()
