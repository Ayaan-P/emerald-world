"""Private 55-move catalog checks; no promotion or gameplay claim."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DONOR = ROOT.parent / 'expansion-foundation/engines/expansion-native'
OUT = ROOT / 'build/rc4-self-drop-move-catalog/generated'
BASELINE = ROOT / 'build/rc4-move-catalog-fixed/generated'
NEW = {
    'MOVE_CLOSE_COMBAT': (406, 'EFFECT_DEF_SPDEF_DOWN_HIT', 120, 'TYPE_FIGHTING', 100, 5),
    'MOVE_HEADLONG_RUSH': (407, 'EFFECT_DEF_SPDEF_DOWN_HIT', 120, 'TYPE_GROUND', 100, 5),
    'MOVE_HAMMER_ARM': (408, 'EFFECT_SELF_SPEED_DOWN_HIT', 100, 'TYPE_FIGHTING', 90, 10),
    'MOVE_ICE_HAMMER': (409, 'EFFECT_SELF_SPEED_DOWN_HIT', 100, 'TYPE_ICE', 90, 10),
}


def stage():
    # Replay the 51-to-55 transition even after the final catalog is promoted.
    # Overlay the coherent manifest/data seed. Integration sources and the
    # generator stay installed files, and frozen baseline bytes are read-only.
    script = '''import pathlib,runpy,sys
from unittest.mock import patch
root,baseline,generator,donor,out=map(pathlib.Path,sys.argv[1:])
read=pathlib.Path.read_text
seed=read(baseline/'tools/expanded_moves/coverage.json')
def overlay(path,*a,**kw):
    if path == root/'tools/expanded_moves/coverage.json':
        return seed
    relative = path.relative_to(root) if path.is_relative_to(root) else None
    if relative and (str(relative).startswith('src/data/expanded_moves/')
                     or str(relative) == 'data/expanded_move_animations.inc'):
        return read(baseline/relative,*a,**kw)
    return read(path,*a,**kw)
sys.argv=[str(generator),'--donor',str(donor),'--output',str(out)]
with patch.object(pathlib.Path,'read_text',overlay):
    runpy.run_path(str(generator),run_name='__main__')
'''
    subprocess.run([sys.executable, '-c', script, str(ROOT), str(BASELINE),
                    str(ROOT / 'tools/expanded_moves/generate.py'), str(DONOR), str(OUT)],
                   cwd=ROOT, check=True, capture_output=True)
    return json.loads((OUT / 'tools/expanded_moves/coverage.json').read_text())


class SelfDropMoveCatalogTests(unittest.TestCase):
    def test_four_actual_donor_moves_use_dedicated_effects_not_generic_hit(self):
        coverage = stage()
        rows = {r['name']: r for r in coverage['effect_supported']}
        self.assertEqual(len(rows), 55)
        data = (OUT / 'src/data/expanded_moves/battle_moves.h').read_text()
        donor = dict(re.findall(r'\[(MOVE_\w+)\] =\s*\{(.*?)\n    \},',
                               (DONOR / 'src/data/moves_info.h').read_text(), re.S))
        for name, (ident, effect, power, typ, accuracy, pp) in NEW.items():
            self.assertEqual((rows[name]['native_id'], rows[name]['effect'], rows[name]['secondary_chance']),
                             (ident, effect, 0))
            body = re.search(r'\['+name+r'\] = \{([^\n]+)', data)[1]
            for key, value in dict(effect=effect, power=power, type=typ, accuracy=accuracy,
                                   pp=pp, secondaryEffectChance=0, target='MOVE_TARGET_SELECTED', priority=0).items():
                self.assertRegex(body, r'\.'+key+r' = '+str(value)+r'[, ]')
            self.assertIn('.self = TRUE', donor[name])
            self.assertIn('.moveEffect = MOVE_EFFECT_STAT_MINUS', donor[name])
            stats = ('defense', 'spDef') if ident < 408 else ('speed',)
            for stat in stats:
                self.assertRegex(donor[name], r'\.'+stat+r' = 1,')
            self.assertNotRegex(donor[name], r'\.chance =')
            self.assertIn('.makesContact = TRUE', donor[name])
            self.assertIn('FLAG_MAKES_CONTACT', body)
            self.assertIn('FLAG_KINGS_ROCK_AFFECTED', body)

    def test_baseline_51_identity_and_explicit_native_policy_metadata(self):
        coverage = stage()
        old = json.loads((BASELINE / 'tools/expanded_moves/coverage.json').read_text())
        self.assertEqual(coverage['effect_supported'][:51], old['effect_supported'])
        for path in (BASELINE / 'src/data/expanded_moves').glob('*.h'):
            relative = path.relative_to(BASELINE)
            self.assertTrue((OUT / relative).read_bytes().startswith(path.read_bytes()), str(relative))
        self.assertTrue((OUT / 'data/expanded_move_animations.inc').read_bytes().startswith(
            (BASELINE / 'data/expanded_move_animations.inc').read_bytes()))
        names = re.findall(r'_\("([^\"]+)"\)', (OUT / 'src/data/expanded_moves/names.h').read_text())
        self.assertEqual(len(names), 55)
        self.assertTrue(all(len(name) <= 12 for name in names))
        self.assertIn('HEADLNG RUSH', names)
        for name in NEW:
            audit = coverage['candidate_audit'][name]
            self.assertEqual(audit['secondary_chance'], 0)
            self.assertIn('self_drop_certain', audit)
            self.assertTrue(audit['self_drop_certain'])
            self.assertEqual(audit['animation_policy'], 'Reused native animation, not donor animation parity')
            self.assertIn('Mist / Clear Body / White Smoke', audit['policy'])
            self.assertIn('native ability set', audit['policy'])
            self.assertEqual(audit['display_name'], 'HEADLNG RUSH' if name == 'MOVE_HEADLONG_RUSH'
                             else name[5:].replace('_', ' '))

    def test_production_effect_table_selects_certain_self_secondaries(self):
        coverage = stage()
        script = (ROOT / 'data/battle_scripts_1.s').read_text()
        table = script.split('gBattleScriptsForMoveEffects::', 1)[1].split('BattleScript_EffectHit::', 1)[0]
        pointers = re.findall(r'ptrvalue (BattleScript_\w+)', table)
        effects = (ROOT / 'include/constants/battle_move_effects.h').read_text()
        secondary = (ROOT / 'include/constants/battle.h').read_text()
        for name, (_, effect, *_) in NEW.items():
            paired = effect == 'EFFECT_DEF_SPDEF_DOWN_HIT'
            ident, label, token, sid = ((214, 'DefSpDefDownHit', 'DEF_SPDEF_DOWN', 60) if paired
                                       else (215, 'SelfSpeedDownHit', 'SELF_SPEED_DOWN', 61))
            self.assertRegex(effects, r'#define '+effect+r'\s+'+str(ident)+r'\b')
            self.assertEqual(pointers[ident], 'BattleScript_Effect'+label)
            body = script.split('BattleScript_Effect'+label+'::', 1)[1].split('goto BattleScript_EffectHit', 1)[0]
            self.assertIn('setmoveeffect MOVE_EFFECT_'+token+' | MOVE_EFFECT_AFFECTS_USER | MOVE_EFFECT_CERTAIN', body)
            self.assertRegex(secondary, r'#define MOVE_EFFECT_'+token+r'\s+'+str(sid)+r'\b')
        self.assertEqual(coverage['move_count'], 410)
        self.assertEqual(len(pointers), 216)


if __name__ == '__main__':
    unittest.main()
