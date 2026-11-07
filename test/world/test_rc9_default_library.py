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
            with patch.object(web_launcher,'DIST',dist), patch.object(Path,'home',return_value=Path('/home/tester')):
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

    def test_vanilla_default_is_unchanged(self):
        self.assertEqual(self.capture_root([]),Path('/home/tester/.local/share/emerald-world/worlds'))

    def test_explicit_root_keeps_existing_engine_namespace(self):
        self.assertEqual(self.capture_root(['--worlds-root','/tmp/worlds','--engine','expansion-native']),
                         Path('/tmp/worlds/engines/expansion-native'))
