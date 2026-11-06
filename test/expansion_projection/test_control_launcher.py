import os
from pathlib import Path
import unittest
from unittest.mock import patch
from world.launcher import game_command, profile_paths

class ControlLaunch(unittest.TestCase):
    def test_expansion_is_opt_in_and_scoped(self):
        root = Path('/tmp/test-expansion-control')
        paths = profile_paths(root, 'Alice', engine='expansion-native')
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                game_command('/tmp/engine', root, paths, agent_control=True, online=False, engine='expansion-native')
        with patch.dict(os.environ, {'EW_EXPERIMENTAL_EXPANSION_CONTROL':'1'}, clear=True):
            args = game_command('/tmp/engine', root, paths, agent_control=True, online=False, engine='expansion-native')
            self.assertEqual(args[args.index('EW_EXPANSION_CONTROL') + 1], str(paths['profile'] / 'player.sock'))
            self.assertEqual(args[args.index('EW_EXPANSION_SAVE') + 1], str(paths['save']))

    def test_offline_expansion_routes_control_flag(self):
        from world.launcher import main
        with patch('world.expansion.run', return_value=0) as run:
            self.assertEqual(main(['--state-dir', '/tmp/world', 'offline', 'Alice',
                                   '--engine', 'expansion-native', '--agent-control']), 0)
            self.assertTrue(run.call_args.args[0].agent_control)
