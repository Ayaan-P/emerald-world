"""Production Mega readiness without private compile or policy overrides."""
import itertools
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from world.rules import NAMES, make, publish, read, validate, wire

ROOT = Path(__file__).resolve().parents[2]


class MegaReadinessTests(unittest.TestCase):
    def test_boolean_policy_matrix_and_vanilla_default(self):
        self.assertEqual(make()['rules'], dict.fromkeys(NAMES, False))
        for flags in itertools.product((False, True), repeat=len(NAMES)):
            rules = dict(zip(NAMES, flags))
            with self.subTest(rules=rules):
                if rules['megaEvolution'] and not rules['modernSplit']:
                    with self.assertRaisesRegex(ValueError, 'Mega Evolution requires modernSplit'):
                        make(rules=rules)
                else:
                    value = make(rules=rules)
                    self.assertEqual(validate(value)['rules'], rules)
                    self.assertEqual(value['mask'], sum(1 << i for i, flag in enumerate(flags) if flag))
        for bad in (0, 1, 'true', None):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'boolean'):
                make(rules=dict.fromkeys(NAMES, False) | {'megaEvolution': bad})

    def test_schema_boolean_dependency_matches_policy_matrix(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT/'world/rules.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for flags in itertools.product((False, True), repeat=len(NAMES)):
            rules = dict(zip(NAMES, flags))
            value = dict(make(), rules=rules,
                         mask=sum(1 << i for i, flag in enumerate(flags) if flag))
            with self.subTest(rules=rules):
                self.assertEqual(validator.is_valid(value),
                                 not rules['megaEvolution'] or rules['modernSplit'])
        for bad in (0, 1, 'true', None):
            with self.subTest(bad=bad):
                value = make(rules=dict.fromkeys(NAMES, False) | {'modernSplit': True})
                value['rules']['megaEvolution'] = bad
                self.assertFalse(validator.is_valid(value))

    def test_native_default_support_and_explicit_unsupported_fail_closed(self):
        source = r'''
#include "platform/world_rules.h"
#include "platform/mega_game.h"
#include <assert.h>
int main(void) {
    assert(WorldRules_Mask() == 0);
    assert(!WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION));
    assert(WorldRules_Init("1:12:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa") == EXPECT_READY);
    assert(WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION) == EXPECT_READY);
    assert(WorldRules_Mask() == (EXPECT_READY ? 12 : 0));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='mega-readiness-c-') as directory:
            root = Path(directory)
            (root/'main.c').write_text(source)
            for name, flags, expected in [('default', [], 1), ('unsupported', ['-DMEGA_FEATURE_READY=0'], 0)]:
                with self.subTest(build=name):
                    binary = root/name
                    result = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-DPORTABLE', '-DVER_64BIT', f'-DEXPECT_READY={expected}', *flags,
                        '-Iinclude', str(root/'main.c'), 'src/platform/world_rules.c',
                        '-o', str(binary)], cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_private_offline_manifest_fails_before_profile_creation(self):
        from world.offline import offline_profile
        from world.rules import MANIFEST
        with tempfile.TemporaryDirectory(prefix='mega-invalid-offline-') as directory:
            root = Path(directory)
            invalid = make()
            invalid['rules']['megaEvolution'] = True
            (root/MANIFEST).write_text(json.dumps(invalid))
            with self.assertRaisesRegex(ValueError, 'Mega Evolution requires modernSplit'):
                with offline_profile(root, 'alice'):
                    self.fail('Invalid Mega policy admitted for offline play')
            self.assertFalse((root/'.offline').exists())

    def test_host_and_private_offline_policy_round_trip(self):
        from world.server import WorldServer
        from world.offline import offline_profile
        from world.launcher import game_command
        with tempfile.TemporaryDirectory(prefix='mega-ready-') as directory:
            root = Path(directory)
            server = WorldServer(root/'world.sock', root)
            try:
                value = server.set_world_rules(dict.fromkeys(NAMES, False) |
                                               {'modernSplit': True, 'megaEvolution': True})
                self.assertEqual(value['mask'], 12)
                self.assertEqual(read(root), value)
                with self.assertRaisesRegex(ValueError, 'Mega Evolution requires modernSplit'):
                    server.set_world_rules(value['rules'] | {'modernSplit': False})
                self.assertEqual(server.world_rules, value)
                self.assertEqual(read(root), value)
            finally:
                server.close()
            with offline_profile(root, 'alice') as paths:
                command = game_command('/bin/true', root/'.offline', paths, online=False)
                self.assertEqual(command[command.index('--world-rules') + 1], wire(value))
                self.assertEqual(read(root), value)
                self.assertFalse(paths['save'].exists())
            with self.assertRaisesRegex(ValueError, 'Mega Evolution requires modernSplit'):
                publish(root, dict(value, rules=value['rules'] | {'modernSplit': False}))
            self.assertEqual(read(root), value)


if __name__ == '__main__':
    unittest.main()
