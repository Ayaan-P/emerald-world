from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/'port/resolved'
class InitialResolutions(unittest.TestCase):
 def read(self,name):
  text=(ROOT/name).read_text();self.assertNotIn('<<<<<<<',text);self.assertNotIn('>>>>>>>',text);return text
 def test_world_and_dexnav_menu_fit(self):
  s=self.read('src/start_menu.c');m=self.read('src/menu.c')
  self.assertIn('sCurrentStartMenuActions[10]',s)
  self.assertIn('[MENU_ACTION_DEXNAV]',s);self.assertIn('[MENU_ACTION_WORLD]',s)
  self.assertIn('sNumStartMenuActions >= 10 ? 13',s);self.assertIn('numActions >= 9 ? 18',m)
 def test_generated_map_hooks_and_donor_warps(self):
  s=self.read('src/overworld.c');f=self.read('src/field_control_avatar.c')
  self.assertIn('GetMapLayout(u16 mapLayoutId)',s);self.assertIn('GeneratedMap_ResolveLayout(gMapLayouts[mapLayoutId - 1])',s)
  self.assertIn('GeneratedMap_Leave()',f);self.assertIn('StorePlayerStateAndSetupWarp(position, warpEventId)',f)
 def test_donor_save_flush_and_world_guard(self):
  s=self.read('src/save.c');self.assertIn('GeneratedMap_IsInside()',s);self.assertIn('frame_flush_save()',s);self.assertNotIn('Platform_StoreSaveFile()',s)
 def test_world_virtual_cable_alias(self):
  s=self.read('src/link.c');self.assertIn('NativeLink_Main1(',s);self.assertIn('GetBlockReceivedSize(u8 who)',s)
 def test_script_special_order_and_unique_dexnav(self):
  e=self.read('data/event_scripts.s');sp=self.read('data/specials.inc')
  self.assertEqual(e.count('.include "data/scripts/dexnav.inc"'),1);self.assertIn('WorldActivity_EventScript_StoragePC::',e);self.assertIn('def_special GeneratedMap_RunEvent',sp)
 def test_bulk_module_provenance_matches_carried_sources(self):
  import hashlib,json
  data=json.loads((ROOT.parent/'world-port-provenance.json').read_text())
  self.assertEqual(len(data['files']),37)
  for item in data['files']:
   self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['merged_sha256'],item['path'])

 def test_carried_engine_hooks(self):
  import hashlib,json
  self.assertIn('WorldBridge_PrepareSave()',self.read('src/fieldmap.c'))
  self.assertIn('ScriptMenu_DrawRepelChoice(',self.read('src/script_menu.c'))
  self.assertIn('GetTaskCount(void)',self.read('src/task.c'))
  data=json.loads((ROOT.parent/'prior-hooks-provenance.json').read_text())
  for item in data['files']:
   self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['merged_sha256'])
