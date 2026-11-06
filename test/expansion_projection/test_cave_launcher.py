import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from world.expansion import ExpansionSession, stage_cave
from world.launcher import game_command, profile_paths

class CaveLaunch(unittest.TestCase):
    def template(self):
        cells=bytearray(b'#'*(31*31))
        for y in range(1,30): cells[y*31+1]=ord('.')
        for x in range(1,30): cells[28*31+x]=ord('.')
        cells[29*31+29]=ord('.')
        return b'EWGMAP01'+cells
    def test_private_staging_and_offline_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); paths=profile_paths(root,'Alice',engine='expansion-native')
            paths['profile'].mkdir(parents=True,mode=0o700)
            source=root/'source'; source.write_bytes(self.template())
            staged=stage_cave(source,paths['profile'])
            self.assertEqual(staged.read_bytes(),self.template())
            self.assertEqual(staged.stat().st_mode & 0o777,0o600)
            with patch.dict(os.environ,{'EW_EXPERIMENTAL_EXPANSION_CAVE':'1'},clear=True):
                args=game_command('/tmp/engine',root,paths,online=False,engine='expansion-native',cave_template=staged)
                self.assertEqual(args[args.index('EW_EXPANSION_CAVE_TEMPLATE')+1],str(staged))
                with self.assertRaises(ValueError): game_command('/tmp/engine',root,paths,online=True,engine='expansion-native',cave_template=staged)
            source.write_bytes(b'EWGMAP01'+b'.'*(31*31))
            with self.assertRaises(ValueError): stage_cave(source,paths['profile'])
    def test_online_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'EW_EXPERIMENTAL_EXPANSION_CAVE':'1'},clear=True):
            session=ExpansionSession(Path(d),'Alice',online=True)
            with self.assertRaises(ValueError): session.run(generated_map=Path('/tmp/not-used'))
