import os
from pathlib import Path
import unittest
from unittest.mock import patch
from world.launcher import game_command, profile_paths
class DexNavLaunch(unittest.TestCase):
 def test_expansion_opt_in_is_explicit(self):
  root=Path('/tmp/dexnav-world'); paths=profile_paths(root,'Alice',engine='expansion-native')
  with patch.dict(os.environ,{},clear=True):
   args=game_command('/tmp/engine',root,paths,online=False,engine='expansion-native')
   self.assertNotIn('EW_EXPERIMENTAL_EXPANSION_DEXNAV',args)
  with patch.dict(os.environ,{'EW_EXPERIMENTAL_EXPANSION_DEXNAV':'1'},clear=True):
   args=game_command('/tmp/engine',root,paths,online=False,engine='expansion-native')
   self.assertEqual(args[args.index('EW_EXPERIMENTAL_EXPANSION_DEXNAV')+1],'1')
