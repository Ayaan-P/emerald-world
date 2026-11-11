"""Executable app integration boundaries; no native gameplay assertions."""
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest

from world import shared_strength
from world.link_sessions import RegionPresence
from world.strength_transaction import INITIAL

ROOT = pathlib.Path(__file__).resolve().parents[1]
FLAGS = ('BIRCH_RESEARCH', 'BIRCH_STUDIES', 'HOENN_MARKETS', 'SHARED_CONTEST',
         'SHARED_STRENGTH', 'RYDEL_ROUTES', 'MATCH_CALL_EVENTS', 'MAP_OFFERS',
         'WALLY_INVITATION')


class StrengthIsolation(unittest.TestCase):
    def setUp(self):
        self.channels = {who: {'id': who} for who in ('a', 'b')}
        self.presence = RegionPresence(
            {'a': (24, 14, 9, 15, 0, 0, 1), 'b': (24, 14, 11, 16, 0, 0, 1)},
            {'a': 'hoenn', 'b': 'hoenn'})
        tag = types.SimpleNamespace(id=3, active=True, participants=('a', 'b'))
        self.server = types.SimpleNamespace(
            link_protocol=types.SimpleNamespace(_tags={3: tag}, _tag_actor={'a': 3, 'b': 3}),
            link_channels=self.channels, _link_presence=lambda: self.presence)

    def send(self, who, text):
        return shared_strength.handle(self.server, self.channels[who], text.encode())

    def join(self):
        frame = shared_strength.encode(INITIAL)
        self.send('a', 'ST JOIN 3 1 ' + frame)
        return self.send('b', 'ST JOIN 3 2 ' + frame)

    def test_same_numeric_map_in_different_registry_cannot_share(self):
        self.presence.scopes['b'] = 'different-registry'
        self.assertEqual(self.join(), [])
        self.assertFalse(self.server._strength_state['rooms'])

    def test_reconnected_channel_cannot_ack_old_transaction(self):
        self.assertEqual(len(self.join()), 2)
        self.assertEqual(len(self.send('a', 'ST PROPOSE 3 1 0 2 10 15 11 15')), 2)
        self.channels['b'] = {'id': 'b'}
        self.send('a', 'ST READY 3 1 1 ' + shared_strength.encode(INITIAL))
        messages = self.send('b', 'ST READY 3 2 1 ' + shared_strength.encode(INITIAL))
        self.assertFalse(any(' COMMIT ' in line for _, line in messages))
        self.assertFalse(self.server._strength_state['rooms'])

    def test_registry_change_closes_admitted_room(self):
        self.assertEqual(len(self.join()), 2)
        self.presence.scopes['b'] = 'other'
        messages = self.send('a', 'ST PROPOSE 3 1 0 2 10 15 11 15')
        self.assertTrue(any(' CLOSED ' in line for _, line in messages))
        self.assertFalse(self.server._strength_state['rooms'])


class BuildOptIn(unittest.TestCase):
    def flags(self, *args):
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, 'Makefile.native').write_text('probe:\n\t@printf "%s\\n" "$(NATIVE_EXTRA_CPPFLAGS)"\n')
            result = subprocess.run(['make', '-s', '-f', str(ROOT / 'engines/expansion.mk'), 'probe', *args],
                                    cwd=directory, text=True, capture_output=True, check=True)
            return result.stdout.split()

    def test_actual_make_expansion_defaults_all_new_flags_and_turn_plan_off(self):
        flags = self.flags()
        for name in (*FLAGS, 'COOP_TURN_PLAN'):
            self.assertIn(f'-DEW_{name}=0', flags)
        self.assertIn('-DEW_REGION_STATE=1', flags)
        self.assertIn('-DEW_KANTO_CONTENT=1', flags)

    def test_actual_make_expansion_can_enable_new_flags_without_turn_plan(self):
        flags = self.flags(*(f'EW_{name}=1' for name in FLAGS))
        for name in FLAGS:
            self.assertIn(f'-DEW_{name}=1', flags)
        self.assertIn('-DEW_COOP_TURN_PLAN=0', flags)

    def test_new_cli_switches_require_explicit_development(self):
        for name in FLAGS:
            option = '--experimental-' + name.lower().replace('_', '-')
            if name == 'SHARED_CONTEST':
                option = '--experimental-shared-contest'
            with self.subTest(option=option):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/build_expansion.py'), option],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn(option + ' requires --development', result.stderr)


if __name__ == '__main__':
    unittest.main()
