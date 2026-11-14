import contextlib,io,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import build_expansion
class Build(unittest.TestCase):
 def test_requires_development(self):
  with patch('sys.argv',['build_expansion.py','--experimental-floorplans']),contextlib.redirect_stderr(io.StringIO()):
   with self.assertRaises(SystemExit) as e:build_expansion.main()
  self.assertEqual(e.exception.code,2)
 def test_default_is_off(self):
  root=Path(__file__).resolve().parents[1]
  self.assertIn('WORLD_FLOORPLANS ?= 0',(root/'engines/expansion.mk').read_text())
  self.assertIn('int(args.experimental_floorplans)',(root/'scripts/build_expansion.py').read_text())
