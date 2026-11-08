"""Default Expansion library must leave room for native Unix socket paths."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
from world import web_launcher
from world.launcher import engine_state, profile_paths, player_endpoint

class RootCaptured(Exception):
    pass

class DefaultLibrary(unittest.TestCase):
    def capture_root(self, args):
        captured=[]
        def capture(path):
            captured.append(path)
            raise RootCaptured()
        with tempfile.TemporaryDirectory() as temp:
            dist=Path(temp);(dist/'index.html').write_text('<html></html>')
            with patch.object(web_launcher,'DIST',dist), patch.object(Path,'home',return_value=Path('/home/tester')), \
                    patch('scripts.linux_client.prerequisites', return_value=[]):
                with patch.object(web_launcher.DesktopSession,'create_root',side_effect=capture):
                    with self.assertRaises(RootCaptured):web_launcher.main(args)
        return captured[0]

    def test_default_expansion_library_fits_real_authority_and_player_addresses(self):
        root=self.capture_root(['--engine','expansion-native'])
        world=root/'local-0123456789ab'
        authority=engine_state(world,'expansion-native')/'transport/world.sock'
        player=player_endpoint(profile_paths(world,'Alice',engine='expansion-native'))
        self.assertLessEqual(len(str(authority).encode()),107)
        self.assertLessEqual(len(str(player).encode()),107)
        self.assertNotEqual(root,Path('/home/tester/.local/share/emerald-world/worlds'))

    def test_source_launcher_defaults_to_expansion(self):
        self.assertEqual(self.capture_root([]),Path('/home/tester/.ew/x'))

    def test_explicit_vanilla_library_is_unchanged(self):
        self.assertEqual(self.capture_root(['--engine','vanilla']),Path('/home/tester/.local/share/emerald-world/worlds'))

    def test_check_is_read_only_and_reports_missing_expansion_binary(self):
        import contextlib
        import io
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(web_launcher, 'DIST', Path(directory)), \
                    patch('scripts.linux_client.discover_binary', return_value=Path(directory)/'pokeemerald-native') as discover, \
                    patch.object(web_launcher.DesktopSession, 'create_root') as create, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(web_launcher.main(['--check']), 1)
            discover.assert_called_once_with('expansion-native')
            create.assert_not_called()
        self.assertIn('scripts/build_expansion.py', output.getvalue())
        self.assertIn('npm ci', output.getvalue())

    def test_explicit_root_keeps_existing_engine_namespace(self):
        self.assertEqual(self.capture_root(['--worlds-root','/tmp/worlds','--engine','expansion-native']),
                         Path('/tmp/worlds/engines/expansion-native'))
