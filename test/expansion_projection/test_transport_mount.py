"""Check the engine-specific sandbox mounts without opening any sockets."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from world.launcher import game_command, profile_paths

class TransportMountTests(unittest.TestCase):
    def test_online_expansion_mounts_only_its_own_transport(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            paths = profile_paths(base, 'Ash', engine='expansion-native')
            transport = base/'engines'/'expansion-native'/'transport'
            transport.mkdir(parents=True)
            with patch.dict('os.environ', {'EW_EXPERIMENTAL_EXPANSION_LINK': '1'}):
                args = game_command(base/'game', base, paths, online=True, engine='expansion-native')
            idx = args.index('EW_EXPANSION_LINK_CONFIG')
            self.assertEqual(args[idx+1], str(paths['config']))
            self.assertIn(['--ro-bind', str(transport), str(transport)], [args[i:i+3] for i in range(len(args)-2)])
            self.assertNotIn(str(base/'transport'), args)
    def test_online_link_is_opt_in(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {}, clear=True):
            base = Path(d)
            paths = profile_paths(base, 'Ash', engine='expansion-native')
            args = game_command(base/'game', base, paths, online=True, engine='expansion-native')
            self.assertNotIn('EW_EXPANSION_LINK_CONFIG', args)
            self.assertNotIn(str(base/'engines'/'expansion-native'/'transport'), args)
    def test_battle_activity_needs_both_transport_and_peer_opt_ins(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); paths = profile_paths(base, 'Ash', engine='expansion-native')
            for env, expected in [({'EW_EXPERIMENTAL_EXPANSION_ACTIVITIES':'1'}, False),
                ({'EW_EXPERIMENTAL_EXPANSION_LINK':'1','EW_EXPERIMENTAL_EXPANSION_ACTIVITIES':'1'}, False),
                ({'EW_EXPERIMENTAL_EXPANSION_LINK':'1','EW_EXPERIMENTAL_EXPANSION_PEERS':'1',
                  'EW_EXPERIMENTAL_EXPANSION_ACTIVITIES':'1'}, True)]:
                with self.subTest(env=env), patch.dict('os.environ', env, clear=True):
                    args = game_command(base/'game', base, paths, online=True, engine='expansion-native')
                    self.assertEqual('EW_EXPERIMENTAL_EXPANSION_ACTIVITIES' in args, expected)
    def test_offline_expansion_has_no_link_transport(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            paths = profile_paths(base, 'Ash', engine='expansion-native')
            args = game_command(base/'game', base, paths, online=False, engine='expansion-native')
            self.assertNotIn('EW_EXPANSION_LINK_CONFIG', args)
            self.assertNotIn(str(base/'engines'/'expansion-native'/'transport'), args)

if __name__ == '__main__': unittest.main()
