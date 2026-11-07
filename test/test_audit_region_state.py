"""Read-only regional script state audit; no ROMs, saves, or sockets."""
import os
from pathlib import Path
import tempfile
import unittest
from scripts.audit_region_state import audit
ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get('EW_RC7_ENGINE', ROOT/'engines/expansion-native'))

class RegionStateAudit(unittest.TestCase):
 def test_real_pallet_state_conflict_and_placeholder(self):
  result=audit(ENGINE)
  self.assertGreater(result['scripts_scanned'],0)
  self.assertTrue(any(r['firered']=='VAR_MAP_SCENE_PALLET_TOWN_OAK' and 'VAR_LITTLEROOT_TOWN_STATE' in r['emerald'] for r in result['direct_variable_collisions']))
  self.assertIn('FLAG_PALLET_LADY_NOT_BLOCKING_SIGN',result['emerald_zero_flag_placeholders'])
 def test_counts_only_referenced_identifiers_and_ignores_comments(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'data/maps/Test_Frlg').mkdir(parents=True);(p/'include/constants').mkdir(parents=True)
   (p/'data/maps/Test_Frlg/scripts.inc').write_text('setvar VAR_KANTO 1\nsetflag FLAG_KANTO\n@ VAR_IGNORED FLAG_IGNORED\n')
   (p/'include/constants/vars.h').write_text('#define VAR_HOENN 0x4050\n#define VAR_UNUSED_0x4051 0x4051\n')
   (p/'include/constants/vars_frlg.h').write_text('#define VAR_KANTO 0x4050\n#define VAR_IGNORED 0x4050\n')
   (p/'include/constants/flags.h').write_text('#define FLAG_KANTO 0\n#define FLAG_IGNORED 0\n')
   result=audit(p)
   self.assertEqual(result['direct_variable_collisions'],[{'firered':'VAR_KANTO','value':'0x4050','emerald':['VAR_HOENN']}])
   self.assertEqual(result['emerald_zero_flag_placeholders'],['FLAG_KANTO'])
 def test_missing_source_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError): audit(d)
