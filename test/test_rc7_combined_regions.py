"""Compile the modified generator and exercise actual RC7 map source offline."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))

class CombinedRegions(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='ew-combined-regions-')
  cls.p=Path(cls.tmp.name);cls.asm=cls.p/'asm';cls.inc=cls.p/'include';cls.asm.mkdir();cls.inc.mkdir()
  src=ENGINE/'tools/mapjson';cls.bin=cls.p/'mapjson'
  q=subprocess.run(['g++','-std=c++17','-O2',str(src/'json11.cpp'),str(src/'mapjson.cpp'),'-o',str(cls.bin)],capture_output=True,text=True)
  if q.returncode: raise RuntimeError(q.stderr)
  args=[str(cls.bin),'layouts','combined','data/layouts/layouts.json',str(cls.asm),str(cls.inc)]
  q=subprocess.run(args,cwd=ENGINE,capture_output=True,text=True)
  if q.returncode: raise RuntimeError(q.stderr)
  args=[str(cls.bin),'groups','combined','data/maps/map_groups.json',*map(str,sorted((ENGINE/'data/maps').glob('*/map.json'))),str(cls.asm),str(cls.inc)]
  q=subprocess.run(args,cwd=ENGINE,capture_output=True,text=True)
  if q.returncode: raise RuntimeError(q.stderr)
 @classmethod
 def tearDownClass(cls): cls.tmp.cleanup()
 def test_hoenn_kanto_and_generated_worlds_are_included(self):
  groups=(self.asm/'groups.inc').read_text();layouts=(self.asm/'layouts.inc').read_text();constants=(self.inc/'map_groups.h').read_text()
  for symbol in ('LittlerootTown', 'PalletTown_Frlg', 'GeneratedWorld_Cave', 'GeneratedWorld_Wilds'): self.assertIn(symbol, groups)
  self.assertIn('PalletTown_Layout::',layouts);self.assertIn('LittlerootTown_Layout::',layouts)
  self.assertIn('MAP_GENERATED_WORLD_CAVE  = (0 | (34 << 8))',constants)
  self.assertIn('MAP_PALLET_TOWN                          = (0 | (38 << 8))',constants)
  pallet=layouts.split('PalletTown_Layout::',1)[1].split('\n\n',1)[0]
  self.assertIn('gTileset_General_Frlg',pallet);self.assertIn('.byte TRUE',pallet)
 def test_real_pallet_header_events_and_connections(self):
  out=self.asm/'PalletTown_Frlg';out.mkdir()
  scratch=self.p/'map-root'; (scratch/'include/constants').mkdir(parents=True)
  (scratch/'include/constants/map_groups.h').write_text((self.inc/'map_groups.h').read_text())
  (scratch/'data').symlink_to((ENGINE/'data').resolve(), target_is_directory=True)
  q=subprocess.run([str(self.bin),'map','combined','data/maps/PalletTown_Frlg/map.json','data/layouts/layouts.json',str(out)],cwd=scratch,capture_output=True,text=True)
  self.assertEqual(q.returncode,0,q.stderr)
  self.assertIn('PalletTown_Frlg_MapScripts',(out/'header.inc').read_text())
  self.assertIn('MAP_ROUTE1',(out/'connections.inc').read_text())
  self.assertIn('PalletTown_EventScript_SignLady',(out/'events.inc').read_text())
 def test_kanto_progress_ids_conflict_with_hoenn(self):
  emerald=(ENGINE/'include/constants/vars.h').read_text();kanto=(ENGINE/'include/constants/vars_frlg.h').read_text()
  self.assertIn('VAR_LITTLEROOT_TOWN_STATE                        0x4050',emerald)
  self.assertRegex(kanto,r'VAR_MAP_SCENE_PALLET_TOWN_OAK\s+0x4050')
  flags=(ENGINE/'include/constants/flags.h').read_text()
  self.assertRegex(flags,r'FLAG_PALLET_LADY_NOT_BLOCKING_SIGN\s+0\b')
