import contextlib,io,unittest
from unittest.mock import patch
from pathlib import Path
from scripts import build_expansion
class NatureBuildTests(unittest.TestCase):
 def test_requires_explicit_development(self):
  err=io.StringIO()
  with patch('sys.argv',['build_expansion.py','--experimental-nature-challenges']),contextlib.redirect_stderr(err):
   with self.assertRaises(SystemExit) as e:build_expansion.main()
  self.assertEqual(e.exception.code,2);self.assertIn('--development',err.getvalue())
 def test_default_off_and_paired_pin(self):
  self.assertEqual(build_expansion.PIN,'fddcf429bd6c93e476a914daac5e3580aa22e6c5')
  root=Path(__file__).resolve().parents[1]
  self.assertIn('WORLD_NATURE_CHALLENGES ?= 0',(root/'engines/expansion.mk').read_text())
  self.assertIn('int(args.experimental_nature_challenges)',(root/'scripts/build_expansion.py').read_text())
