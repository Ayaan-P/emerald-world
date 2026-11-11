import contextlib,io,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import build_expansion
class Build(unittest.TestCase):
 def test_development_required(self):
  with patch('sys.argv',['build_expansion.py','--experimental-native-trades']),contextlib.redirect_stderr(io.StringIO()):
   with self.assertRaises(SystemExit) as e:build_expansion.main()
  self.assertEqual(e.exception.code,2)
 def test_flag_default_off(self):
  root=Path(__file__).resolve().parents[1]
  self.assertIn('WORLD_TRADE_OFFERS ?= 0',(root/'engines/expansion.mk').read_text())
  self.assertIn('int(args.experimental_native_trades)',(root/'scripts/build_expansion.py').read_text())
